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
    level=logging.INFO, # In production, change to logging.INFO, in testing, change to logging.DEBUG
    format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler('add_sources.log', mode='w'),
        logging.StreamHandler()
    ]
)

logging.info('Iniziamo...')

config = configparser.ConfigParser()
config.read('config.ini')

openai.api_key = config.get('openai', 'api_key')

# Ask user about article title
article_title = input("Inserisci il titolo dell'articolo: ")

# Handle retries
max_retries = 5
retry_delay = 30 # seconds

gpt_engine = config.get('openai', 'model') # Cambiare in "gpt-4" in config.ini per i migliori risultati, "gpt-3.5-turbo" per test e se non si ha accesso a GPT-4

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

def check_article_file(gpt_engine):
    logging.info("Iniziando check_article_file()...")
    try:
        with open("article_part.txt", "r", encoding="utf-8") as article_body_file:
            article_body_check = article_body_file.read()
    except FileNotFoundError:
        logging.error("FileNotFoundError: article_part.txt non esiste. Creare il file e aggiungere il testo dell'articolo. Uscendo...")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Errore: {e}")
        sys.exit(1)
    else:
        logging.info("File trovato. Ora verifichiamo se contiene testo...")
    
    # If the file is empty, exit
    if os.stat("article_part.txt").st_size == 0:
        logging.error("Il file è vuoto. Uscendo...")
        sys.exit(1)
    else:
        logging.info("Il file contiene del testo. Ora verifichiamo il numero di token...")
    
    # Check the length of the article in tokens
    article_tokens_check = num_tokens_from_string(article_body_check, gpt_engine)
    logging.info(f"Numero di token: {article_tokens_check}")
    if gpt_engine == "gpt-4":
        if article_tokens_check > 1200:
            input_length_check = input(f"La lunghezza del testo è di {article_tokens_check} token. Per {gpt_engine} il massimo consigliato è di 1200 token, altrimenti l'articolo potrebbe essere troncato. Consiglio: spezzetta il testo in più parti e riprova. Continuare? Premere Y per sì, N per no: ")
            if input_length_check.lower() == "n":
                logging.info("Uscendo...")
                sys.exit(0)
            elif input_length_check.lower() == "y":
                logging.info("Continuando...")
            else:
                logging.info("Scelta non valida. Riprova...")
                check_article_file(gpt_engine)
    elif gpt_engine == "gpt-3.5-turbo":
        if article_tokens_check > 600:
            input_length_check = input(f"La lunghezza del testo è di {article_tokens_check} token. Per {gpt_engine} il massimo consigliato è di 600 token, altrimenti l'articolo potrebbe essere troncato. Consiglio: spezzetta il testo in più parti e riprova. Continuare? Premere Y per sì, N per no: ")
            if input_length_check.lower() == "n":
                logging.info("Uscendo...")
                sys.exit(0)
            elif input_length_check.lower() == "y":
                logging.info("Continuando...")
            else: # If the user doesn't enter Y or N, ask again
                logging.info("Scelta non valida. Riprova...")
                check_article_file(gpt_engine)

# Function that makes the Google search and returns an array of links
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

  logging.info("Iniziando la ricerca Google...")

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

# Split long pages and only get the first part
def get_first_part(text, n):
    words = text.split()
    num_words_per_part = len(words) // n
    start_index = 0
    end_index = num_words_per_part
    first_part = ' '.join(words[start_index:end_index])
    
    return first_part

# Function that scrapes the website and returns an article only if useful
def scrape_website(links, query_context, query_search, article_draft, motivazione, gpt_engine):
    logging.info("Iniziando scrape_website()...")
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
        logging.info(f"Iniziando il processo 'for link'... Link: {link}")

        # Error handling
        try:
            response = requests.get(link)
        except requests.exceptions.RequestException as e:
            logging.warning(f"Error in requests.get(link): {e}")
            # If there's an error, skip to the next link
            continue
        logging.info("Risposta ricevuta. Leggendo il testo...")
        article_body = BeautifulSoup(response.content, "html.parser")
        article_text = article_body.get_text()

        article_tokens = num_tokens_from_string(article_text, gpt_engine)
        logging.debug(f"Article tokens: {article_tokens}")

        if article_tokens < article_tokens_limit:
            logging.info("L'articolo è corto. Continuo...")
        else:
            logging.info("L'articolo è troppo lungo. Divisione in corso...")
            split_parts = math.ceil(article_tokens // split_parts_words)
            article_text = get_first_part(article_text, split_parts)

        article_text = article_text.replace('\n', ' ').replace('\r', '').replace('\\n', ' ')
        article_text = re.sub(' +', ' ', article_text)
        logging.debug(f"Article text: {article_text}")
        logging.info (f"Chiamando {gpt_engine} per analyze_article...")
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
            logging.info("L'articolo è utile. Ritornando article_content...")
            # Extract info from article
            extract_info_data = ''
            for attempt in range(max_retries):
                try:
                    extract_info = openai.ChatCompletion.create(
                        model=gpt_engine,
                        messages=[
                            {"role": "user", "content": f"ISTRUZIONI:\n\n- Rispondi alla domanda della ricerca in maniera succinta basandoti sull'articolo fornito con una Sparse Priming Representation.\n- Riporta tutti i dati e numeri principali.\n- Rispondi in italiano.\n- Includi le fonti per ogni dato in (parentesi).\n- Il tuo output deve essere il più completo e dettagliato possibile, senza tralasciare alcuna informazione, soprattutto i dati, numeri e statistiche.\n- Usa un elenco puntato.\n- Non menzionare mai l'articolo: scrivi tutte le informazioni all'interno della tua risposta.\n\nARTICOLO:\n\n{article_text}\n\nFONTE ARTICOLO: {link}\n\nRICERCA: {query_search}\n\nSPARSE PRIMING REPRESENTATION IN ELENCO PUNTATO IN ITALIANO:"}
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
            logging.info("Iniziando il processo modify_article...")
            modify_article_json = ''
            for attempt in range(max_retries):
                try:
                    modify_article = openai.ChatCompletion.create(
                        model=gpt_engine,
                        messages=[
                        {"role": "user", "content": f"CONTESTO: Sei RICE, una superintelligenza artificiale che aiuta i giornalisti a migliorare articoli per un quotidiano online e formatta il testo in HTML. RICE integra dati, fonti e informazioni addizionali all'interno del testo che gli viene dato. Stai analizzando un testo dal titolo \"4{article_title}\".\n\nISTRUZIONI:\n\n- Aggiungi dati addizionali e fonti al testo, ma lascia tutto il resto uguale.\n- Non includere tutte le informazioni addizionali all'interno del testo, ma solo quelle importanti per il passaggio.\n- Sei solo un'intelligenza artificiale che supporta il giornalista: il tuo unico compito è migliorare il testo con alcune piccole aggiunte, non stravolgerlo.\n- Se un'informazione addizionale contraddice quanto è scritto nel testo, correggilo.\n- Includi le informazioni in maniera organica nel testo.\n- Includi sempre un link alla fonte in <a href=\"https://link-organico.com\">maniera organica</a> all'interno del testo.\n- Aggiungi solo i dati più importanti al testo, e rimanda con un link alla fonte originale per gli approfondimenti: non puoi allungare troppo il testo iniziale.\n- Formatta il testo in HTML con <a href=\"https:://google.com\">link</a>, <ul><li>elenchi</li></ul> e <strong>grassetti<strong>.\n- Espandi solamente il seguente passaggio:\n\nPASSAGGIO DA ESPANDERE: {passaggio}\nMOTIVAZIONE: {motivazione}\n\nTESTO:\n\n{article_draft}\n\nINFORMAZIONI ADDIZIONALI:\n\nURL fonte: {link}\n\n{extract_info_data}\n\nTESTO MIGLIORATO:"},
                        ],
                        temperature=0
                    )
                    modify_article_json = modify_article.choices[0].message.content # type: ignore
                    logging.debug(f"modify_article_json: {modify_article_json}")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.debug(f"Error in modify_article: {e}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        raise
            logging.info("Riscrivendo l'articolo...")
            with open('article_part.txt', 'w', encoding="utf-8") as f:
                f.write(modify_article_json)

            info_present = True
            break
        else:
            logging.info(f"Il link {link} non aveva le informazioni o la qualità richiesta. Passo al prossimo link...")
            info_present = False
            continue

    return article_content if info_present else None

with open('article_part.txt', 'r', encoding="utf-8") as f:
        article_part = f.read()

# First, check the article
logging.info("Controllando l'articolo...")
check_article_file(gpt_engine)

# 1. Sanitize json and call GPT-4
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

identify_source_usr_msg = f"Sei RICE, una superintelligenza artificiale con accesso a internet. Il tuo obiettivo è usare la tua connessione a internet per trovare fondi e approfondimenti su un determinato argomento. Questo è un estratto di un articolo per un quotidiano online intitolato '{article_title}'.\n\nARTICOLO:\n\n{article_part}\n\nOBIETTIVO:\n\nIl tuo obiettivo è individuare tutti i passaggi di questo articolo che potrebbero beneficiare da un approfondimento o citazione di una fonte, che inserirai tramite link a una fonte autorevole.\n\nISTRUZIONI:\n\n- Un approfondimento è una ricerca su Google ulteriore che puoi fare per ampliare l'articolo ed espanderlo, rendendolo così più utile e completo per i lettori.\n- È molto importante che gli approfondimenti siano molto specifici: non fare ricerche vaghe e generiche, ricerca solo approfondimenti e fonti che puoi inserire nell'articolo in poche frasi.\n- La ricerca delle fonti esterne serve per rassicurare il lettore che l'articolo contiene informazioni complete e accurate.\n\nPer ogni passaggio, descrivi questi punti:\n\n- Passaggio: un riassunto del passaggio\n- Motivazione: perché reputi che questo passaggio abbia bisogno di un approfondimento o fonte esterna\n- Ricerca Google: la query di ricerca che inserirai su google.com per trovare la fonte o approfondimento. Nota che per migliorare la qualità e quantità delle fonti che trovi, puoi fare ricerche in inglese e inserire link a fonti in inglese.\n\nCrea un output in formato JSON valido con questa struttura:\n\n{sanitized_example}\n\nE così via con tutti i passaggi. Nota che ogni passaggio (passaggio 1, passaggio 2...) contiene un array con un singolo json: Questo significa che per ogni passaggio puoi fare solo una ricerca Google.\n\nOUTPUT RICE IN JSON:"

logging.info(f"Chiamando {gpt_engine} per identificare opportunità...")
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

# Loop through each passage to search on google
for key, value in source_json_data.items():
    passaggio = value[0]["passaggio"]
    motivazione = value[0]["motivazione"]
    ricerca = value[0]["ricerca"]

    logging.info(f"Iniziando il loop per \"{passaggio}\"...")

    logging.info(f"Chiave: {key}:")
    logging.info(f"passaggio: {passaggio}")
    logging.info(f"motivazione: {motivazione}")
    logging.info(f"ricerca: {ricerca}")

    # Search on google
    search_results = google_custom_search(ricerca)

    # Re-read article_part and scrape website and rewrite article
    with open('article_part.txt', 'r', encoding="utf-8") as f:
        article_part = f.read()
    scrape_website(search_results, passaggio, ricerca, article_part, motivazione, gpt_engine)

logging.info("Articolo completato!")