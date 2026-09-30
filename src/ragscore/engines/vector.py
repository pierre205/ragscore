"""Moteur integre : mesurer un corpus vectorise, sans application a brancher.

Il existe deux facons de mesurer, et elles ne repondent pas a la meme question.

Brancher l'API reellement livree dit si LE PRODUIT est bon. C'est la mesure qui compte
avant de vendre, et aucune reimplementation ne la remplace : deux chemins de requete
divergent des qu'on touche a l'un, et l'evaluation finit par noter autre chose.

Ce moteur-ci dit si UNE APPROCHE est bonne : ce decoupage, ce modele d'embeddings, ce
reranker. C'est la mesure qu'on veut en amont, quand l'application n'existe pas encore, ou
pour comparer deux strategies sans rien deployer. Il ne demande qu'une base vectorisee et
deux cles.

Un rapport produit par ce moteur ne doit donc jamais etre presente comme la mesure du
produit : il porte le nom du moteur, et son libelle le rappelle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ragscore.connector import ConnectorError, resolveEnvironment
from ragscore.system import Answer, RetrievalStage, RetrievedPassage

DEFAULT_SYSTEM_PROMPT = (
    "Tu reponds a partir des seuls extraits fournis.\n"
    "Cite systematiquement l'identifiant du document dont vient chaque information.\n"
    "Si les extraits ne contiennent pas la reponse, dis-le clairement et ne l'invente pas."
)


@dataclass
class VectorEngine:
    """Recherche vectorielle, reclassement, generation. Tout est declare, rien n'est code."""

    name: str
    kind: str = "vector"
    # Connexion a la base. Ecrivez « {{env:NOM}} » : une URL porte un mot de passe.
    databaseUrl: str = "{{env:DATABASE_URL}}"
    table: str = "chunk"
    # Quand l'identifiant ne vit pas dans la meme table que le texte (cas frequent : les
    # extraits d'un cote, le document de l'autre), on donne ici la relation complete, avec
    # sa jointure. C'est du SQL assume, comme « whereClause » : de la configuration, jamais
    # une valeur saisie par un utilisateur final.
    fromClause: str = ""
    # Peut etre qualifie : « document.code ».
    identifierColumn: str = "code"
    textColumn: str = "content"
    embeddingColumn: str = "embedding"
    # Quand l'identifiant n'est pas une colonne mais une expression : une cle JSONB
    # (« metadata->>'url' »), une concatenation, un cast. Prioritaire sur la colonne.
    # SQL assume, comme « fromClause » : de la configuration, pas une saisie d'utilisateur.
    identifierExpression: str = ""
    textExpression: str = ""
    # Une clause SQL ajoutee au filtrage, sans parametre utilisateur (ex. « lang = 'fr' »).
    whereClause: str = ""
    searchLimit: int = 40
    rerankKeep: int = 8
    maxPassages: int = 14
    embeddingModel: str = "voyage-3.5"
    rerankModel: str = "rerank-2.5"
    generationModel: str = "claude-sonnet-5"
    maxOutputTokens: int = 2000
    systemPrompt: str = DEFAULT_SYSTEM_PROMPT
    voyageApiKey: str = "{{env:VOYAGE_API_KEY}}"
    anthropicApiKey: str = "{{env:ANTHROPIC_API_KEY}}"
    # Tarifs en dollars par million de jetons, pour que le rapport annonce ce qu'il a coute.
    inputPricePerMillion: float = 2.0
    outputPricePerMillion: float = 10.0

    def describe(self) -> str:
        return (
            f"moteur integre | {self.fromClause or self.table} "
            f"({self.identifierExpression or self.identifierColumn}, "
            f"{self.textExpression or self.textColumn}) "
            f"| {self.embeddingModel} + {self.rerankModel} + {self.generationModel}"
        )


SEARCH_STAGE = "recherche"
RERANK_STAGE = "rerank"


def importDependencies():
    """Les dependances du moteur sont optionnelles : le harnais s'utilise sans elles."""
    try:
        import anthropic
        import psycopg
        import voyageai
        from pgvector.psycopg import register_vector
    except ModuleNotFoundError as missing:
        raise ConnectorError(
            f"le moteur integre a besoin de dependances supplementaires ({missing.name}) :\n"
            '    uv pip install "ragscore[engine]"'
        ) from missing
    return psycopg, register_vector, voyageai, anthropic


@dataclass
class Passage:
    identifier: str
    text: str


@dataclass
class VectorEngineSystem:
    """Le systeme mesurable obtenu a partir d'un moteur declare."""

    engine: VectorEngine
    _connection: object | None = field(default=None, init=False, repr=False)
    _voyage: object | None = field(default=None, init=False, repr=False)
    _anthropic: object | None = field(default=None, init=False, repr=False)

    def open(self) -> None:
        if self._connection is not None:
            return
        psycopg, register_vector, voyageai, anthropic = importDependencies()
        engine = self.engine
        try:
            self._connection = psycopg.connect(resolveEnvironment(engine.databaseUrl))
            register_vector(self._connection)
        except Exception as connectionFailure:
            raise ConnectorError(
                f"connexion a la base impossible : {connectionFailure}"
            ) from connectionFailure
        self._voyage = voyageai.Client(api_key=resolveEnvironment(engine.voyageApiKey))
        self._anthropic = anthropic.Anthropic(api_key=resolveEnvironment(engine.anthropicApiKey))

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # ------------------------------------------------------------------ etages
    def searchCandidates(self, question: str) -> list[Passage]:
        import psycopg
        from psycopg import sql

        engine = self.engine
        try:
            embedded = self._voyage.embed(
                [question], model=engine.embeddingModel, input_type="query"
            )
        except Exception as embeddingFailure:
            raise ConnectorError(
                f"la vectorisation de la question a echoue "
                f"({type(embeddingFailure).__name__}) : {embeddingFailure}"
            ) from embeddingFailure
        vector = embedded.embeddings[0]

        # Les noms de table et de colonnes viennent d'une saisie : ils sont composes en
        # identifiants SQL, jamais concatenes, et la clause « where » est la seule partie
        # libre, assumee comme telle et sans valeur utilisateur.
        relation = (
            sql.SQL(engine.fromClause)
            if engine.fromClause
            else sql.Identifier(*engine.table.split("."))
        )
        query = sql.SQL(
            "SELECT {identifier}, {text} FROM {relation} {filter} "
            "ORDER BY {embedding} <=> %s LIMIT %s"
        ).format(
            identifier=(
                sql.SQL(engine.identifierExpression)
                if engine.identifierExpression
                else sql.Identifier(*engine.identifierColumn.split("."))
            ),
            text=(
                sql.SQL(engine.textExpression)
                if engine.textExpression
                else sql.Identifier(*engine.textColumn.split("."))
            ),
            relation=relation,
            filter=sql.SQL(f"WHERE {engine.whereClause}") if engine.whereClause else sql.SQL(""),
            embedding=sql.Identifier(*engine.embeddingColumn.split(".")),
        )
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(query, (str(vector), engine.searchLimit))
                rows = cursor.fetchall()
        except psycopg.Error as queryFailure:
            self._connection.rollback()
            raise ConnectorError(
                f"la recherche a echoue : {queryFailure}. Verifiez le nom de la table et "
                "des colonnes dans la configuration du moteur."
            ) from queryFailure
        return [Passage(identifier=str(row[0]), text=str(row[1])) for row in rows]

    def rerankCandidates(self, question: str, candidates: list[Passage]) -> list[Passage]:
        if not candidates:
            return []
        engine = self.engine
        try:
            reranked = self._voyage.rerank(
                query=question,
                documents=[passage.text for passage in candidates],
                model=engine.rerankModel,
                top_k=min(engine.rerankKeep, len(candidates)),
            )
        except Exception as rerankFailure:
            raise ConnectorError(
                f"le reclassement a echoue ({type(rerankFailure).__name__}) : {rerankFailure}"
            ) from rerankFailure
        return [candidates[result.index] for result in reranked.results]

    def generate(self, question: str, passages: list[Passage]) -> tuple[str, int, int]:
        engine = self.engine
        extracts = "\n\n".join(
            f"[{passage.identifier}]\n{passage.text}"
            for passage in passages[: engine.maxPassages]
        )
        try:
            message = self._anthropic.messages.create(
                model=engine.generationModel,
                max_tokens=engine.maxOutputTokens,
                system=engine.systemPrompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Extraits :\n\n{extracts}\n\nQuestion : {question}",
                    }
                ],
            )
        except Exception as generationFailure:
            # Une trace brute d'exception traversait l'interface. Les deux causes
            # courantes (solde epuise, modele inconnu) meritent d'etre dites en clair :
            # ce ne sont pas des defauts du systeme mesure, et les confondre ferait
            # chercher au mauvais endroit.
            raise ConnectorError(
                f"la generation a echoue ({type(generationFailure).__name__}) : "
                f"{generationFailure}"
            ) from generationFailure
        text = "".join(block.text for block in message.content if block.type == "text")
        return text, message.usage.input_tokens, message.usage.output_tokens

    # ------------------------------------------------------------------ contrat
    def answer(self, question: str) -> Answer:
        self.open()
        engine = self.engine
        candidates = self.searchCandidates(question)
        retained = self.rerankCandidates(question, candidates)
        text, inputTokens, outputTokens = self.generate(question, retained)

        submitted = retained[: engine.maxPassages]
        return Answer(
            text=text,
            stages=[
                RetrievalStage(SEARCH_STAGE, uniqueInOrder(candidates)),
                RetrievalStage(RERANK_STAGE, uniqueInOrder(submitted)),
            ],
            # Exactement ce qui a ete soumis au generateur, dans l'ordre : c'est ce dont un
            # outil de jugement de contenu a besoin, et rien d'autre ne le remplace.
            passages=[
                RetrievedPassage(identifier=passage.identifier, text=passage.text)
                for passage in submitted
            ],
            inputTokens=inputTokens,
            outputTokens=outputTokens,
            estimatedCostUsd=(
                inputTokens * engine.inputPricePerMillion
                + outputTokens * engine.outputPricePerMillion
            )
            / 1_000_000,
        )


def uniqueInOrder(passages: list[Passage]) -> list[str]:
    """Un document cite par plusieurs passages ne compte qu'une fois, a son meilleur rang.

    Sans cette reduction, le rang mesure la position d'un PASSAGE, pas celle du document,
    et deux passages de la meme fiche feraient chuter le rang sans qu'aucune recuperation
    ne soit en cause.
    """
    identifiers: list[str] = []
    for passage in passages:
        if passage.identifier not in identifiers:
            identifiers.append(passage.identifier)
    return identifiers
