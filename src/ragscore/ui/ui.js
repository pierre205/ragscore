// Interface de ragscore. Sans cadriciel ni dependance distante : la page doit s'ouvrir
// meme hors ligne, et rester lisible par quelqu'un qui n'a jamais vu le projet.

const element = (identifier) => document.getElementById(identifier)
const etat = { connectors: [], caseSets: [], reports: [], dernierRapport: null }

// ------------------------------------------------------------------ utilitaires

function afficherAvis(cible, message, genre = "erreur") {
    const conteneur = element(cible)
    conteneur.textContent = ""
    if (!message) return
    const boite = document.createElement("div")
    boite.className = `avis ${genre}`
    boite.textContent = message
    conteneur.append(boite)
}

function lireJson(valeur, defaut) {
    if (!valeur.trim()) return defaut
    return JSON.parse(valeur)
}

async function appeler(url, options) {
    const reponse = await fetch(url, options)
    const charge = await reponse.json()
    if (!reponse.ok) throw new Error(charge.error || `erreur ${reponse.status}`)
    return charge
}

// ------------------------------------------------------------------ etages

function rangeeEtage(etage = { name: "", source: "", itemField: "" }) {
    const rangee = document.createElement("div")
    rangee.className = "rangee-etage"
    const champs = [
        { cle: "name", texte: "Nom de l'étage", valeur: etage.name, exemple: "rerank" },
        { cle: "source", texte: "Événement ou chemin", valeur: etage.source, exemple: "sources" },
        { cle: "itemField", texte: "Champ", valeur: etage.itemField || "", exemple: "code" },
    ]
    for (const champ of champs) {
        const bloc = document.createElement("div")
        const etiquette = document.createElement("label")
        etiquette.textContent = champ.texte
        const saisie = document.createElement("input")
        saisie.value = champ.valeur
        saisie.placeholder = champ.exemple
        saisie.dataset.cle = champ.cle
        bloc.append(etiquette, saisie)
        rangee.append(bloc)
    }
    const retrait = document.createElement("button")
    retrait.type = "button"
    retrait.textContent = "Retirer"
    retrait.addEventListener("click", () => rangee.remove())
    rangee.append(retrait)
    return rangee
}

function lireEtages() {
    return [...element("etages").children]
        .map((rangee) => {
            const valeurs = {}
            for (const saisie of rangee.querySelectorAll("input")) {
                valeurs[saisie.dataset.cle] = saisie.value.trim()
            }
            return valeurs
        })
        .filter((etage) => etage.name && etage.source)
        .map((etage) => ({
            name: etage.name,
            source: etage.source,
            itemField: etage.itemField || null,
            payloadPath: "",
        }))
}

// ------------------------------------------------------------------ connecteur

const CONSIGNE_PAR_DEFAUT =
    "Tu reponds a partir des seuls extraits fournis.\n" +
    "Cite systematiquement l'identifiant du document dont vient chaque information.\n" +
    "Si les extraits ne contiennent pas la reponse, dis-le clairement et ne l'invente pas."

function lireMoteur() {
    const entier = (identifiant) => parseInt(element(identifiant).value, 10)
    return {
        kind: "vector",
        name: element("nom").value.trim(),
        databaseUrl: element("base-url").value.trim(),
        table: element("table").value.trim(),
        identifierColumn: element("colonne-id").value.trim(),
        textColumn: element("colonne-texte").value.trim(),
        embeddingColumn: element("colonne-vecteur").value.trim(),
        whereClause: "",
        searchLimit: entier("limite"),
        rerankKeep: entier("garde"),
        maxPassages: entier("passages"),
        embeddingModel: element("modele-embed").value.trim(),
        rerankModel: element("modele-rerank").value.trim(),
        generationModel: element("modele-gen").value.trim(),
        maxOutputTokens: 2000,
        systemPrompt: element("invite").value.trim() || CONSIGNE_PAR_DEFAUT,
        voyageApiKey: element("cle-voyage").value.trim(),
        anthropicApiKey: element("cle-anthropic").value.trim(),
        inputPricePerMillion: 2,
        outputPricePerMillion: 10,
    }
}

function ecrireMoteur(moteur) {
    const poser = (identifiant, valeur) => { element(identifiant).value = valeur ?? "" }
    poser("nom", moteur.name)
    poser("base-url", moteur.databaseUrl)
    poser("table", moteur.table)
    poser("colonne-id", moteur.identifierColumn)
    poser("colonne-texte", moteur.textColumn)
    poser("colonne-vecteur", moteur.embeddingColumn)
    poser("limite", moteur.searchLimit)
    poser("garde", moteur.rerankKeep)
    poser("passages", moteur.maxPassages)
    poser("modele-embed", moteur.embeddingModel)
    poser("modele-rerank", moteur.rerankModel)
    poser("modele-gen", moteur.generationModel)
    poser("cle-voyage", moteur.voyageApiKey)
    poser("cle-anthropic", moteur.anthropicApiKey)
    poser("invite", moteur.systemPrompt || CONSIGNE_PAR_DEFAUT)
}

function majSorte() {
    const moteur = element("sorte").value === "vector"
    element("formulaire-http").hidden = moteur
    element("formulaire-vector").hidden = !moteur
    if (moteur && !element("invite").value) element("invite").value = CONSIGNE_PAR_DEFAUT
}

function lireDeclaration() {
    return element("sorte").value === "vector" ? lireMoteur() : lireConnecteur()
}

function lireConnecteur() {
    const authUrl = element("auth-url").value.trim()
    return {
        kind: "http",
        name: element("nom").value.trim(),
        url: element("url").value.trim(),
        mode: element("mode").value,
        method: element("methode").value,
        headers: {},
        body: lireJson(element("corps").value, {}),
        textSource: element("texte-source").value.trim(),
        textField: element("texte-champ").value.trim(),
        stages: lireEtages(),
        usage: {
            source: element("usage-source").value.trim(),
            inputTokensPath: "inputTokens",
            outputTokensPath: "outputTokens",
            costPath: "estimatedCostUsd",
        },
        authentication: authUrl
            ? { url: authUrl, method: "POST", body: lireJson(element("auth-corps").value, {}), headers: {} }
            : null,
        timeoutSeconds: 180,
        errorSource: "error",
        errorMessagePath: "message",
    }
}

function ecrireConnecteur(connecteur) {
    element("nom").value = connecteur.name || ""
    element("url").value = connecteur.url || ""
    element("mode").value = connecteur.mode || "sse"
    element("methode").value = connecteur.method || "POST"
    element("corps").value = JSON.stringify(connecteur.body || {}, null, 2)
    element("texte-source").value = connecteur.textSource || ""
    element("texte-champ").value = connecteur.textField || ""
    element("usage-source").value = (connecteur.usage && connecteur.usage.source) || ""
    element("auth-url").value = (connecteur.authentication && connecteur.authentication.url) || ""
    element("auth-corps").value = connecteur.authentication
        ? JSON.stringify(connecteur.authentication.body || {}, null, 2)
        : element("auth-corps").value
    element("etages").textContent = ""
    for (const etage of connecteur.stages || []) element("etages").append(rangeeEtage(etage))
    majLibellesMode()
}

function majLibellesMode() {
    const flux = element("mode").value === "sse"
    element("label-texte-source").textContent = flux ? "Événement du texte" : "Chemin du texte"
    element("texte-champ").parentElement.style.display = flux ? "" : "none"
}

// ------------------------------------------------------------------ etat general

function remplirListe(identifiant, valeurs, libelle) {
    const liste = element(identifiant)
    const choixPrecedent = liste.value
    liste.textContent = ""
    for (const valeur of valeurs) {
        const option = document.createElement("option")
        option.value = valeur.value
        option.textContent = libelle(valeur)
        liste.append(option)
    }
    if (valeurs.some((valeur) => valeur.value === choixPrecedent)) liste.value = choixPrecedent
}

async function rafraichir() {
    const donnees = await appeler("/api/state")
    Object.assign(etat, donnees)
    element("racine").textContent = donnees.root
    remplirListe(
        "jeu",
        donnees.caseSets.map((jeu) => ({ value: jeu.name, ...jeu })),
        (jeu) => `${jeu.name} — ${jeu.total} cas${jeu.refusals ? `, dont ${jeu.refusals} refus` : ""}`,
    )
    remplirListe(
        "connecteur",
        [{ value: "", name: "" }, ...donnees.connectors.map((item) => ({ value: item.name, ...item }))],
        (item) => item.name || "nouveau connecteur",
    )
    afficherRapports()
}

function afficherRapports() {
    const conteneur = element("rapports")
    conteneur.textContent = ""
    if (!etat.reports.length) {
        conteneur.append(Object.assign(document.createElement("p"), {
            className: "discret", textContent: "aucune mesure enregistrée pour l'instant",
        }))
        return
    }
    const table = document.createElement("table")
    table.append(enTete(["rapport", "date", "réussis"]))
    for (const rapport of etat.reports) {
        const ligne = document.createElement("tr")
        ligne.append(
            cellule(rapport.name, "mono"),
            cellule((rapport.generatedAt || "").replace("T", " ").replace("+00:00", "")),
            cellule(rapport.passed == null ? "—" : `${rapport.passed}/${rapport.total}`),
        )
        conteneurCliquable(ligne, rapport)
        table.append(ligne)
    }
    conteneur.append(table)
}

function conteneurCliquable(ligne, rapport) {
    ligne.style.cursor = "pointer"
    ligne.addEventListener("click", () => {
        etat.dernierRapport = rapport.name
        afficherMesures(rapport.summary)
        afficherAvis("avis-mesure", `rapport « ${rapport.name} » chargé`, "info")
    })
}

function enTete(colonnes) {
    const ligne = document.createElement("tr")
    for (const colonne of colonnes) {
        const cellule = document.createElement("th")
        cellule.textContent = colonne
        ligne.append(cellule)
    }
    return ligne
}

function cellule(contenu, classe = "") {
    const cellule = document.createElement("td")
    cellule.textContent = contenu
    if (classe) cellule.className = classe
    return cellule
}

// ------------------------------------------------------------------ resultats

const POURCENTAGES = {
    citedRelevant: "document cité",
    mustIncludeSatisfied: "valeur attendue",
    refusalCorrect: "refus corrects",
    noForbiddenValue: "aucune valeur interdite",
}

function afficherMesures(resume) {
    const conteneur = element("mesures")
    conteneur.textContent = ""
    if (!resume) return

    const mesures = [
        { nom: "cas réussis", valeur: `${resume.passed}/${resume.casesTotal}` },
        ...Object.entries(resume.recallByStage || {}).map(([nom, valeur]) => ({
            nom: `trouvé après « ${nom} »`, valeur: `${(valeur * 100).toFixed(1)} %`,
        })),
        { nom: "MRR", valeur: resume.meanReciprocalRank.toFixed(3) },
        { nom: "nDCG", valeur: resume.normalisedDiscountedGain.toFixed(3) },
        ...Object.entries(POURCENTAGES).map(([cle, nom]) => ({
            nom, valeur: `${(resume[cle] * 100).toFixed(1)} %`,
        })),
    ]
    if (resume.usage && resume.usage.estimatedCostUsd) {
        mesures.push({ nom: "coût mesuré", valeur: `${resume.usage.estimatedCostUsd.toFixed(3)} $` })
    }

    for (const mesure of mesures) {
        const carte = document.createElement("div")
        carte.className = "mesure"
        carte.append(
            Object.assign(document.createElement("div"), { className: "valeur", textContent: mesure.valeur }),
            Object.assign(document.createElement("div"), { className: "nom", textContent: mesure.nom }),
        )
        conteneur.append(carte)
    }
}

function nouvelleLigneCas(donnees) {
    const ligne = document.createElement("tr")
    const pastille = document.createElement("span")
    pastille.className = `pastille ${donnees.succeeded ? "ok" : "ko"}`
    pastille.textContent = donnees.succeeded ? "ok" : "KO"
    const premiere = document.createElement("td")
    premiere.append(pastille)
    ligne.append(
        premiere,
        cellule(donnees.identifier, "mono"),
        cellule(donnees.question.length > 90 ? `${donnees.question.slice(0, 90)}…` : donnees.question),
        cellule(donnees.rank == null ? "—" : `rang ${donnees.rank}`),
    )
    return ligne
}

// ------------------------------------------------------------------ actions

async function deposer(fichier) {
    const contenu = await fichier.text()
    try {
        const resultat = await appeler("/api/cases", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: fichier.name, content: contenu }),
        })
        await rafraichir()
        element("jeu").value = resultat.name
        const sansValeur = resultat.withoutExpectedValue
        afficherAvis(
            "avis-jeu",
            `${resultat.total} cas lus, dont ${resultat.refusals} cas de refus.` +
                (sansValeur ? ` ${sansValeur} cas n'attendent aucune valeur : seule la récupération y sera notée.` : ""),
            "info",
        )
        afficherApercu(resultat.preview)
    } catch (erreurLecture) {
        afficherAvis("avis-jeu", erreurLecture.message)
    }
}

function afficherApercu(cas) {
    const conteneur = element("apercu")
    conteneur.textContent = ""
    if (!cas || !cas.length) return
    const table = document.createElement("table")
    table.append(enTete(["cas", "question", "attendu"]))
    for (const item of cas) {
        const ligne = document.createElement("tr")
        ligne.append(
            cellule(item.identifier, "mono"),
            cellule(item.question.length > 70 ? `${item.question.slice(0, 70)}…` : item.question),
            cellule(item.relevantIdentifiers.join(", ") || "refus attendu", "mono"),
        )
        table.append(ligne)
    }
    conteneur.append(table)
}

async function lancer() {
    const connecteur = element("connecteur").value
    const jeu = element("jeu").value
    if (!connecteur || !jeu) {
        afficherAvis("avis-mesure", "choisissez un jeu de questions et un connecteur enregistré")
        return
    }
    element("lancer").disabled = true
    element("detail").textContent = ""
    element("mesures").textContent = ""
    afficherAvis("avis-mesure", "")

    const table = document.createElement("table")
    table.append(enTete(["", "cas", "question", "rang"]))
    element("detail").append(table)

    const flux = new EventSource(
        `/api/run?connector=${encodeURIComponent(connecteur)}&cases=${encodeURIComponent(jeu)}`,
    )
    let total = 0

    flux.addEventListener("start", (evenement) => {
        total = JSON.parse(evenement.data).total
        element("etat").textContent = `0 / ${total}`
    })
    flux.addEventListener("case", (evenement) => {
        const donnees = JSON.parse(evenement.data)
        table.append(nouvelleLigneCas(donnees))
        element("progression").style.width = `${(donnees.position / total) * 100}%`
        element("etat").textContent = `${donnees.position} / ${total}`
        element("detail").scrollTop = element("detail").scrollHeight
    })
    flux.addEventListener("done", async (evenement) => {
        const donnees = JSON.parse(evenement.data)
        etat.dernierRapport = donnees.report
        afficherMesures(donnees.summary)
        afficherAvis("avis-mesure", `mesure terminée, rapport « ${donnees.report} »`, "info")
        element("lancer").disabled = false
        flux.close()
        await rafraichir()
    })
    flux.addEventListener("error", (evenement) => {
        const message = evenement.data ? JSON.parse(evenement.data).message : "connexion interrompue"
        afficherAvis("avis-mesure", message)
        element("lancer").disabled = false
        flux.close()
    })
}

async function renoter() {
    if (!etat.dernierRapport) {
        afficherAvis("avis-mesure", "aucun rapport à renoter : lancez d'abord une mesure")
        return
    }
    try {
        const resultat = await appeler("/api/rescore", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ report: etat.dernierRapport, cases: element("jeu").value }),
        })
        afficherMesures(resultat.summary)
        afficherAvis("avis-mesure", "renoté sans aucun appel au système, donc sans coût", "info")
    } catch (erreurRenotation) {
        afficherAvis("avis-mesure", erreurRenotation.message)
    }
}

// ------------------------------------------------------------------ demarrage

element("depot").addEventListener("click", () => element("fichier").click())
element("fichier").addEventListener("change", (evenement) => {
    if (evenement.target.files[0]) deposer(evenement.target.files[0])
})
for (const nom of ["dragenter", "dragover"]) {
    element("depot").addEventListener(nom, (evenement) => {
        evenement.preventDefault()
        element("depot").classList.add("survol")
    })
}
for (const nom of ["dragleave", "drop"]) {
    element("depot").addEventListener(nom, (evenement) => {
        evenement.preventDefault()
        element("depot").classList.remove("survol")
    })
}
element("depot").addEventListener("drop", (evenement) => {
    const fichier = evenement.dataTransfer.files[0]
    if (fichier) deposer(fichier)
})

element("ajouter-etage").addEventListener("click", () => element("etages").append(rangeeEtage()))
element("mode").addEventListener("change", majLibellesMode)

element("connecteur").addEventListener("change", () => {
    const choisi = etat.connectors.find((item) => item.name === element("connecteur").value)
    if (!choisi) return
    element("sorte").value = choisi.kind || "http"
    majSorte()
    if (choisi.kind === "vector") ecrireMoteur(choisi)
    else ecrireConnecteur(choisi)
})

element("sorte").addEventListener("change", majSorte)

element("enregistrer").addEventListener("click", async () => {
    try {
        const connecteur = lireDeclaration()
        if (!connecteur.name) throw new Error("un nom est nécessaire")
        if (connecteur.kind === "vector" ? !connecteur.databaseUrl : !connecteur.url) {
            throw new Error("une URL est nécessaire")
        }
        await appeler("/api/connectors", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(connecteur),
        })
        await rafraichir()
        element("connecteur").value = connecteur.name
        afficherAvis("avis-connecteur", "connecteur enregistré", "info")
    } catch (erreurEnregistrement) {
        afficherAvis("avis-connecteur", erreurEnregistrement.message)
    }
})

element("supprimer").addEventListener("click", async () => {
    const nom = element("connecteur").value
    if (!nom) return
    await fetch(`/api/connectors/${encodeURIComponent(nom)}`, { method: "DELETE" })
    await rafraichir()
    afficherAvis("avis-connecteur", "connecteur supprimé", "info")
})

element("tester").addEventListener("click", async () => {
    const conteneur = element("resultat-test")
    conteneur.textContent = ""
    afficherAvis("avis-connecteur", "")
    let question = "Question de test"
    const jeuChoisi = etat.caseSets.find((jeu) => jeu.name === element("jeu").value)
    if (jeuChoisi) {
        const apercu = element("apercu").querySelector("td + td")
        if (apercu) question = apercu.textContent.replace(/…$/, "")
    }
    const saisie = window.prompt("Question à envoyer au système :", question)
    if (!saisie) return
    try {
        const resultat = await appeler("/api/connectors/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ connector: lireDeclaration(), question: saisie }),
        })
        const bloc = document.createElement("div")
        bloc.className = "avis info"
        const etages = resultat.stages
            .map((etage) => `${etage.name} : ${etage.documentIdentifiers.join(", ") || "(vide)"}`)
            .join(" | ")
        bloc.textContent = `${etages || "aucun étage détecté"} — réponse de ${resultat.text.length} caractères`
        const extrait = document.createElement("pre")
        extrait.className = "mono"
        extrait.style.whiteSpace = "pre-wrap"
        extrait.textContent = resultat.text.slice(0, 600)
        conteneur.append(bloc, extrait)
    } catch (erreurTest) {
        afficherAvis("avis-connecteur", erreurTest.message)
    }
})

element("lancer").addEventListener("click", lancer)
element("renoter").addEventListener("click", renoter)

majSorte()
rafraichir().catch((erreurDemarrage) => afficherAvis("avis-mesure", erreurDemarrage.message))
