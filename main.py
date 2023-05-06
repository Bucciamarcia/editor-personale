# 1. Viene passato article_part.txt per simulare quello che viene passato da 2_clean_trascript.
# 2. Va chiamato GPT-4 per creare un JSON con le fonti da creare.
# 3. Loop in cui si chiamano le API di Google per cercare le fonti.
# 4. Il primo articolo viene passato a GPT-4 per vedere se è utile. Se lo è, si esce dal loop. Se non lo è, si passa all'articolo successivo finché non viene trovato un articolo utile (ne basta uno).
# 5. Si ripete per tutte le fonti della prima chiamata a GPT.
# 6. Alla fine, article_part.txt sarà stato modificato più volte dao ogni parte del loop, e conterrà tutte le informazioni addizionali ricercate.

import openai
import logging
import json
import requests
import configparser
from bs4 import BeautifulSoup
import tiktoken
import math
import time
import re
import os
import sys

# Initial settings

logging.basicConfig(
    level=logging.DEBUG, # In production, change to logging.INFO, in testing, change to logging.DEBUG
    format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler('add_sources.log', mode='w'),
        logging.StreamHandler()
    ]
)

logging.info('Starting...')

config = configparser.ConfigParser()
config.read('config.ini')

openai.api_key = config.get('openai', 'api_key')

# Get variables from sys.argv
article_title = sys.argv[1]
article_body_arg = sys.argv[2]

# Create article body file
with open("article_part.txt", "w", encoding="utf-8") as article_body_file:
    article_body_file.write(article_body_arg)

# Handle retries
max_retries = 5
retry_delay = 30 # seconds

gpt_engine = "gpt-3.5-turbo" # Change to "gpt-4" in production, "gpt-3.5-turbo" for testing

# Define article split lengths based on engine.
if gpt_engine == "gpt-4":
    article_tokens_limit = 5000
else:
    article_tokens_limit = 2500

if  gpt_engine == "gpt-4":
    split_parts_words = 2500
else:
    split_parts_words = 1250

# Defining functions

# Functions that makes the Google search and returns an array of links
def google_custom_search(query):
  url = 'https://customsearch.googleapis.com/customsearch/v1'
  params = {
    'num': '5',
    'q': query,
    'safe': 'off',
    'prettyPrint': 'true',
    'key': config.get('google_custom_search', 'apikey'),
    'cx': config.get('google_custom_search', 'cx'),
  }
  headers = {'Accept': 'application/json'}

  logging.info("Starting the Google search...")

  google_response = requests.get(url, params=params, headers=headers)
  google_response_json = json.loads(google_response.text)
  links = [item['link'] for item in google_response_json['items']]

  logging.debug(f"Google response: {google_response_json}")

  return links

# Tiktoken
def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

# Split long text and only get the first part
def get_first_part(text, n):
    words = text.split()
    num_words_per_part = len(words) // n
    start_index = 0
    end_index = num_words_per_part
    first_part = ' '.join(words[start_index:end_index])
    
    return first_part

# Function that scrapes the website and returns an article only if useful
def scrape_website(links, query_context, query_search, article_draft):
    logging.info("Starting scrape_website()...")
    article_content = ''
    info_present = False

    sanitized_example_2 = json.dumps('''
    {
      "attendibile": "la fonte è attendibile? Valore booleano True/False",
      "informazione-presente": "il risultato di ricerca fornisce una risposta alla domanda di ricerca? Valore booleano True/False.",
      "motivazione": "motivazione per la tua scelta in informazione-presente"
    }
    ''')

    for link in links:
        logging.info(f"Starting 'for link' subprocess... Link: {link}")

        # Error handling
        try:
            response = requests.get(link)
        except requests.exceptions.RequestException as e:
            logging.warning(f"Error in requests.get(link): {e}")
            # If there's an error, skip to the next link
            continue
        logging.info("Response received. Parsing with BeautifulSoup...")
        article_body = BeautifulSoup(response.content, "html.parser")
        article_text = article_body.get_text()

        article_tokens = num_tokens_from_string(article_text, gpt_engine)
        logging.debug(f"Article tokens: {article_tokens}")

        if article_tokens < article_tokens_limit:
            logging.info("Article is short enough. Continuing...")
        else:
            logging.info("Article is long. Splitting...")
            split_parts = math.ceil(article_tokens // split_parts_words)
            article_text = get_first_part(article_text, split_parts)

        article_text = article_text.replace('\n', ' ').replace('\r', '').replace('\\n', ' ')
        article_text = re.sub(' +', ' ', article_text)
        logging.debug(f"Article text: {article_text}")
        logging.info ("Calling GPT-4 for analyze_article...")
        analyze_article_json = ''
        for attempt in range(max_retries):
            try:
                analyze_article = openai.ChatCompletion.create(
                    model=gpt_engine,
                    messages=[
                        {"role": "system", "content": "Sei un giornalista esperto che filtra la qualità dei risultati di ricerca che gli vengono forniti."},
                        {"role": "user", "content": f"Sei un giornalista ed editor per un quotidiano. Il tuo lavoro è scremare i risultati di ricerca Google che ti vengono presentati, separando quelli di alta qualità che contengono le informazioni richieste, da quelli che sono invece intuili. RISULTATO RICERCA GOOGLE: {link}\n\n{article_text}\n\nOBIETTIVO: Crea un output in formato JSON valido con questa struttura:\n\n{sanitized_example_2}\n\nDOMANDA DI RICERCA: {query_search}\n\nJSON:"},
                    ],
                    temperature=0
                )
                analyze_article_json = analyze_article.choices[0].message.content # type: ignore
                break # If the API call is successful, exit the loop
            except Exception as e:
                if attempt < max_retries - 1:  # If it's not the last attempt, wait and retry
                    logging.debug(f"Error in analyze_article: {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise  # If it's the last attempt, raise the exception
        logging.debug(f"analyze_article_json: {analyze_article_json}")
        analyze_article_json_data = json.loads(analyze_article_json)
        attendibile = analyze_article_json_data['attendibile']
        informazione_presente = analyze_article_json_data['informazione-presente']

        if (attendibile is True or str(attendibile).lower() == 'true') and \
        (informazione_presente is True or str(informazione_presente).lower() == 'true'):
            logging.info("Article is useful. Returning article_content...")
            # Extract info from article
            extract_info_data = ''
            for attempt in range(max_retries):
                try:
                    extract_info = openai.ChatCompletion.create(
                        model=gpt_engine,
                        messages=[
                            {"role": "user", "content": f"PREMESSA:\n\nSono un giornalista e ho bisogno del tuo aiuto per analizzare fonti e approfondimenti per migliorare il mio articolo.\n\nISTRUZIONI:\n\nTi fornirò un articolo e un contesto. Il contesto riguarda le informazioni che desidero approfondire. La ricerca è ciò che devi cercare ed estrapolare dall'articolo. Il tuo output sarà una rappresentazione dettagliata di ciò che l'articolo afferma riguardo al contesto e alla ricerca. Ignora gli altri argomenti. Forniscimi tutte le informazioni necessarie per migliorare il mio articolo senza dover consultare la fonte originale. Rispondi in italiano. Includi le fonti per ogni dato. Il tuo output deve essere il più completo e dettagliato possibile, senza tralasciare alcuna informazione, soprattutto i dati, numeri e statistiche. Usa un elenco puntato.\n\nNon rimandare mai all'articolo: scrivi tutte le informazioni all'interno della tua rappresentazione dettagliata.\n\nARTICOLO:\n\n{article_text}\n\nCONTESTO: {query_context}\n\nRICERCA: {query_search}\n\nRAPRESENTAZIONE DETTAGLIATA:"}
                        ],
                        temperature=0
                    )
                    extract_info_data = extract_info.choices[0].message.content # type: ignore
                    break # If the API call is successful, exit the loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.debug(f"Error in extract_info: {e}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        raise
            logging.debug(f"extract_info_data: {extract_info_data}")

            # Modify the article
            logging.info("Starting modify_article subprocess...")
            modify_article_json = ''
            for attempt in range(max_retries):
                try:
                    modify_article = openai.ChatCompletion.create(
                        model=gpt_engine,
                        messages=[
                        {"role": "user", "content": f"CONTESTO:\n\nSei un editor e giornalista per un quotidiano online.\n\nISTRUZIONI:\n\nIl tuo lavoro è analizzare la bozza scritta dal tuo collaboratore, e migliorarla includendo le informazioni addizionali che ti vengono date:\n\n- Bozza: la bozza dell'articolo scritta dal tuo collaboratore. Basati su questa bozza, ma modificala a tuo piacere includendo le informazioni addizionali.\n- Informazioni addizionali: il contesto addizionale che devi integrare nel tuo articolo completo.\n\nNon sei obbligato a inserire tutto il contesto nella tua versione riscritta: sta a te decidere cosa inserire e cosa no, e dove inserirlo all'interno dell'articolo; il tuo obiettivo è scrivere un articolo completo, informativo e dettagliato dal titolo \"{article_title}\".\n\nSe un'informazione addizionale contraddice quanto è scritto nella bozza, correggi la bozza.\n\nIncludi le informazioni in maniera organica, in modo che l'articolo sia facile da leggere, diretto, semplice ma allo stesso tempo completo e informativo. Includi sempre un link alla fonte ({link}) utilizzando il tag HTML `<a href>`. Utilizza tag HTML come <h2> e <h3> per i sottotitoli, <a href> per linkare la fonte, <b> per sottolineare i punti improtanti, eccetera. Nota che le informazioni addizionali potrebbe riportare una fonte ulteriore: in questo caso, includila sempre il nome della fonte in maniera organica all'interno dell'articolo finito.\n\nBOZZA:\n\n{article_draft}\n\nINFORMAZIONI ADDIZIONALI:\n\nURL fonte: {link}\n\n{extract_info_data}\n\nARTICOLO RISCRITTO:"},
                        ],
                        temperature=0
                    )
                    modify_article_json = modify_article.choices[0].message.content # type: ignore
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.debug(f"Error in modify_article: {e}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        raise
            logging.debug(f"modify_article_json: {modify_article_json}")
            logging.info("Rewriting the article...")
            with open('article_part.txt', 'w', encoding="utf-8") as f:
                f.write(modify_article_json)

            info_present = True
            break
        else:
            logging.info(f"The link {link} didn't have the info or quality desired. Moving on to the next one...")
            info_present = False
            continue

    return article_content if info_present else None

with open('article_part.txt', 'r', encoding="utf-8") as f:
        article_part = f.read()

# 2. Sanitize json and call GPT-4
sanitized_example = json.dumps('''
{
  "passaggio 1": [
    {
      "passaggio": "riassunto del passaggio 1",
      "motivazione": "tua motivazione",
      "ricerca": "tua ricerca google"
    }
  ],
  "passaggio 2": [
    {
      "passaggio": "riassunto del passaggio 2",
      "motivazione": "tua motivazione",
      "ricerca": "tua ricerca google"
    }
  ]
}
''')

identify_source_usr_msg = f"Sei RICE, una superintelligenza artificiale con accesso a internet. Il tuo obiettivo è usare la tua connessione a internet per trovare fondi e approfondimenti su un determinato argomento. Questo è un estratto di un articolo intitolato 'Email marketing e ROI elevato'.\n\nARTICOLO:\n\n{article_part}\n\nOBIETTIVO:\n\nIl tuo obiettivo è individuare tutti i passaggi di questo articolo che potrebbero beneficiare da un approfondimento o citazione di una fonte, che inserirai tramite link a una fonte autorevole.\nEsempio di approfondimento. Un approfondimento può essere ad esempio, se l'articolo menziona che la fame nel mondo sta diminuendo, puoi cercare statistiche e numeri a riguardo per ampliare l'articolo. Insomma, un approfondimento è una ricerca ulteriore che puoi fare per ampliare l'articolo ed espanderlo, rendendolo così più utile e completo per i lettori. È molto importante che gli approfondimenti siano molto specifici: ignora approfondimenti troppo generici. Esempio di approfondimento troppo generico (da non inserire): 'Come creare contenuti di valore nell'email marketing'. Esempio di approfondimento sufficientemente specifico: 'Case study di newsletter di email marketing con contenuti di valore nel settore B2B SAAS'.\n\nEsempio di fonte esterna. La ricerca delle fonti esterne serve per rassicurare il lettore che l'articolo contiene informazioni complete e accurate. Per ogni passaggio, descrivi questi punti:\n\n- Passaggio: un riassunto del passaggio\n- Motivazione: perché reputi che questo passaggio abbia bisogno di un approfondimento o fonte esterna\n- Ricerca Google: la query di ricerca che inserirai su google.com per trovare la fonte o approfondimento. Nota che per migliorare la qualità e quantità delle fonti che trovi, puoi fare ricerche in inglese e inserire link a fonti in inglese.\n\nCrea un output in formato JSON valido con questa struttura:\n\n{sanitized_example}\n\nE così via con tutti i passaggi. Nota che ogni passaggio (passaggio 1, passaggio 2...) contiene un array con un singolo json: Questo significa che per ogni passaggio puoi fare solo una ricerca Google.\n\nOUTPUT RICE IN JSON:"

logging.info("Calling GPT-4 to identify opportunities...")
identify_source_opportunities_json = ''
for attempt in range(max_retries):
    try:
        identify_source_opportunities = openai.ChatCompletion.create(
            model=gpt_engine,
            messages=[
                {"role": "user", "content": identify_source_usr_msg},
            ],
            temperature=0
        )
        identify_source_opportunities_json = identify_source_opportunities.choices[0].message.content # type: ignore
        break
    except Exception as e:
        if attempt < max_retries - 1:
            logging.debug(f"Error in identify_source_opportunities: {e}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            raise
logging.debug(f"identify_source_opportunities_json: {identify_source_opportunities_json}")
source_json_data = json.loads(identify_source_opportunities_json)

# 3. Loop through each passage to search on google
for key, value in source_json_data.items():
    passaggio = value[0]["passaggio"]
    motivazione = value[0]["motivazione"]
    ricerca = value[0]["ricerca"]

    logging.info(f"Looping through \"{passaggio}\"...")

    logging.info(f"{key}:")
    logging.info(f"passaggio: {passaggio}")
    logging.info(f"motivazione: {motivazione}")
    logging.info(f"ricerca: {ricerca}")

    # 4. Search on google
    search_results = google_custom_search(ricerca)

    # 5. Re-read article_part and scrape website and rewrite article
    with open('article_part.txt', 'r', encoding="utf-8") as f:
        article_part = f.read()
    scrape_website(search_results, passaggio, ricerca, article_part)

logging.info("Article completed!")

# 6. Print article part for 2_clean_transcript
with open('article_part.txt', 'r', encoding="utf-8") as f:
    finished_article = f.read()
print(finished_article)

# 7. Delete article_part.txt
os.remove("article_part.txt")