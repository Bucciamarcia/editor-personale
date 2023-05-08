# Editor Personale

Questo è un semplice progetto Creato per ampliare le potenzialità di GPT con un accesso a Google.

## Introduzione

Editor Personale è uno script che usa GPT-3.5-turbo (ChatGPT) o GPT-4 per migliorare un articolo e trovare fonti tramite una serie di ricerche su Google. Particolarmente utile per blogger che vogliono aggiungere automaticamente materiale al propio post, trovare fonti, e aggiungere dati e statistiche.

## Installazione

### Requisiti

- Python 3.10
- Una chiave API di OpenAI (bisogna registrare un account [qui](https://platform.openai.com/signup).)
- Un motore di ricerca Google personalizzato da [questo indirizzo, copiare l'ID, o CX](https://programmablesearchengine.google.com/controlpanel/create).
- Custom Search API da Google Cloud: [link](https://console.cloud.google.com/apis/credentials/key/)

### Installare e usare Editor Personale (per esperti)

- `git clone` della repo.
- `cd editor-personale` per entrare nella cartella di lavoro.
- `pip install -r requirements.txt`.
- Rinominare `config.ini.template` in `config.ini` e inserire la chiave OpenAI, e i dati del motore di ricerca personalizzato Google.
- Rinominare `article_part.txt.template` in `article_part.txt`.
- Inserire il testo che si vuole far elaborare da Editor Personale in `article_part.txt`.
- Se hai accesso a gpt-4, cambiare "model" in config.ini da gpt-3.5-turbo a gpt-4
- Lanciare lo script con `python main.py`.
- Lo script chiederà il titolo dell'articolo per avere del contesto addizionale e milgiorare il risutato finale.
- Lo script aggiornerà sempre lo stesso file, `article_part.txt`, con l'articolo migliorato.

### Installare e usare Editor Personale (per principianti)

Per semplificare la vita a chi non conosce il mondo della programmazione, questo video spiega come installare e usare lo script (compreso Python):

<a href="http://www.youtube.com/watch?feature=player_embedded&v=mZuONTa47kg
" target="_blank"><img src="http://img.youtube.com/vi/mZuONTa47kg/0.jpg" 
alt="IMAGE ALT TEXT HERE" width="240" height="180" border="10" /></a>

## Editor Personale in dettaglio

### Cosa fa Editor Personale in dettaglio?

- Legge l'articolo che gli viene fornito, e trova automaticamente passaggi sui quali può aggiungere informazioni o trovare fonti.
- Per ogni passaggio, esegue una ricerca su Google e legge il primo risultato.
- Se il primo risultato non contiene informazioni rilevanti, passa al secondo risultato e così via finché non trova una fonte rilevante per il passaggio che vuole ampliare.
- Riscrive l'articolo includendo le informazioni addizionali che ha trovato su internet (la fonte viene linkata).
- La ricerca su Google viene fatta in inglese, perché in inglese si trovano una marea di informazioni in più rispetto all'italiano, quindi le fonti linkate saranno in inglese. Ma l'articolo verrà riscritto in italiano.
- Questo processo viene ripetuto per tutti i passaggi che secondo Editor Personale hanno bisogno di una fonte o di un approfondimento.

### Quale modello di GPT dovrei usare?

Se ne hai accesso, consiglio fortemente di usare GPT-4 come modello: i risultati sono nettamente migliori. Ma lo script funziona anche su GPT-3.5-turbo per chi non ha accesso a GPT-4 o vuole fare dei test veloci dello script.

NOTA: di default, lo script usa GPT-3.5-turbo. Si può cambiare in `config.ini`.

### Limitazioni

- C'è un limite di token abbastanza stretto: 600 token per gpt-3.5-turbo, e 1200 per gpt-4. La ragione è che in testo iniziale verrà ampliato parecchio nell'elaborazione, e servono anche tanti token per fornire il contesto. Se hai un articolo lungo, dividilo in pezzi e passali nello script uno a uno.
- Sopratutto con gpt-3.5-turbo, a volte i risultati non sono completamente soddisfacenti, quindi sempre rileggere prima di pubblicare!
- In teoria, l'articolo dovrebbe essere formattato in HTML. Ma questo non sempre avviene soprattutto con gpt-3.5-turbo. Si può aggirare questo problema dando come input un testo già formattato in HTML in `article_part.txt`.
- Questa è la prima versione dello script. L'ho testato con qualche articolo, ma non più di tanto. Quindi di sicuro ci saranno bug e in certi casi i risultati potrebbero essere totalmente sbagliati.
- `add_sources.log` contiene un log completo, in caso di problemi consultare quello e aprire una Issue su Github se il problema persiste (per vedere tutti i log, in `main.py`, cambiare da `level=logging.INFO` a `level=logging.DEBUG`)

## Come collaborare al progetto

Grazie per essere interessato a collaborare a Editor Personale! Qualsiasi collaborazione è sempre ben accetta. Ecco come collaborare:

1. Se vuoi correggere un bug o suggerire un miglioramento, apri una Issue su GitHub per discutere della modifica o dell'aggiunta che vorresti fare al progetto. Questo permette di coordinare meglio gli sforzi e assicurarsi che le modifiche siano in linea con gli obiettivi del progetto.
1. Dopo aver discusso l'Issue, esegui un fork della repository cliccando sul pulsante "Fork" nella parte superiore destra della pagina del progetto su GitHub.
1. Clona la tua fork sul tuo computer locale usando `git clone`.
1. Crea un nuovo branch per la tua funzionalità o correzione con `git checkout -b nome-del-tuo-branch`.
1. Apporta le modifiche necessarie al codice e aggiungi i tuoi commit.
1. Esegui un push del tuo branch sul tuo fork remoto con `git push origin nome-del-tuo-branch`.
1. Vai alla pagina della repository originale su GitHub e crea una nuova Pull Request collegandola all'Issue aperta precedentemente.

Ricorda di seguire le best practice di programmazione e di mantenere il codice pulito e ben documentato. Aggiungi commenti a valanga, quelli non fanno mai male!

Se hai domande o suggerimenti, puoi sempre aprire un Issue su Github per parlarne.