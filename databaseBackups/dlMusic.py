from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from ytmusicapi import YTMusic
import time
import sqlite3
from sqlite3 import Error
import pathlib
import yt_dlp
import os
import requests

#https://open.spotify.com/playlist/37i9dQZF1DXbS5WTN5nKF7




#xpath is the XPATH to the lowest element containig all the musics
xpath = "/html/body/div[3]/div/div[2]/div[6]/div/div[2]/div[1]/div/main/section/div[2]/div[3]/div/div[1]/div/div[2]/div[1]"
#        /html/body/div[3]/div/div[2]/div[6]/div/div[2]/div[1]/div/main/section/div[2]/div[3]/div/div[1]/div/div[2]/div[2]/div[1]



#Select which browser to use when scraping
def select_browser(browser_name):
    return webdriver.Firefox()

#Open the playlist link
def open_playlist(driver, link):
    driver.get(link)

#Wait for "element" to be shown on screen, if the time exceed "max_time" stop and return a timeout
def wait_until_shown(driver, elem_type, element, max_time):
    try : 
        if elem_type =="CSS_SELECTOR" :
            WebDriverWait(driver, max_time).until(EC.visibility_of_element_located((By.CSS_SELECTOR, element)))
        elif elem_type == "CLASS" :
            WebDriverWait(driver, max_time).until(EC.presence_of_element_located((By.CLASS_NAME, element)))
        print(element," has been found on page\n")
    except Exception as e:
        print("TIMEOUT : waited :  ", max_time, "\n\n",e)


#Entry : string
#Output : Int of the first series of numbers
#Example : "sdf459sdf4" -> 459
def extractnbr(text):
    nbr = 0
    i=0
    for l in text :
        try : 
            int(l)
            i+=1
        except :
            break
    nbr=int(text[:i])
    return nbr

#Outputs the numbers of musics inside of a spotify playlist
def getInfo(driver, link):
    nbr = 0 
    isSpotify = False
    try :
        wait_until_shown(driver,"CLASS", "jQEzizWq_N0wiIS3", 20)
        element_nbr = driver.find_element(By.CLASS_NAME, "jQEzizWq_N0wiIS3")
        try :
            driver.find_element(By.CLASS_NAME, "lBNjRAMrqbOebmsh")
        except : 
            print("Playlist from Spotify")
            isSpotify = True
        
        nbr = extractnbr(element_nbr.text)
        
        
    except Exception as e :
        print("Failed :", e)
    return nbr, isSpotify

#Gets all of the musics id of the missing ones in the list musics
def getmissing(musics):
    total = []
    for i in range(len(musics)):
        if musics[i][1] == None :
            total.append(i)
    return total


#Scroll jusqu'à la musique numéro track_index
def scroll_to_track(driver, track_index: int):
    driver.execute_script("""
    const container = document.querySelectorAll("[data-overlayscrollbars-viewport]")[1];
    container.scrollTop = arguments[0] * 56;
""", track_index)

def scrapAllMusic(driver, musics, covers, thumbnail, nbr, end, isSpotify):
    elements, elements_text, elements_number = [],[],[]
    try :
        elements = []
        wait_until_shown(driver,"CSS_SELECTOR", '[data-testid="tracklist-row"]', 20)
        elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tracklist-row"]')
        elements_text = [el.text for el in elements]
        elements_number = [extractnbr(el) for el in elements_text]
        
        for j in range(len(elements)):
            songNbrinPlaylist = elements_number[j]
            if musics[songNbrinPlaylist-1][1] == None:
                musics[songNbrinPlaylist-1][1] = breakit(elements_text[j])
                try:
                    covers[songNbrinPlaylist-1][1] = scrap_cover(driver, elements[j])
                except StaleElementReferenceException:
                    # Full re-fetch, restart from scratch
                    return scrapAllMusic(driver, musics, covers, thumbnail, nbr, end, isSpotify)
                    
        if songNbrinPlaylist == nbr:
            end = True
                
        #scroll_to_track(driver, elements_text[-1])
        if end == False or end == True:
            #driver.execute_script("arguments[0].scrollIntoView();", elements[-1])
            scroll_to_track(driver, elements_number[-6])
        
    except Exception as e: 
        print("\n \nERROR scrapAllMusic  \n", e)
        #end = True
    
    return musics,covers,end
        


#With the playlist, scrap all the musics. Returns a list containing all the musics name, artist, album & duration 
#CHANGER LE MOYEN DE PRENDRE LES IMAGES
#OUVRIR CHACUNE DES MUSIQUES ET PRENDRE TOUTES LES IMAGES A LA FIN        
def scrap_playlist(driver, link, thumbnail):
    end = False
    nbr, isSpotify = getInfo(driver, link)
    musics = [None]*nbr
    covers = [None]*nbr
    for i in range(nbr):
        musics[i]=[i, None]
        covers[i]=[i, None]
    
    while not end:
        musics, covers, end = scrapAllMusic(driver, musics, covers, thumbnail, nbr, end, isSpotify)
        
    missing_id = getmissing(musics)
    print(missing_id)
    for i in missing_id:
        #driver.execute_script("window.scrollTo(0, " + str(music_size*i + 200) +")")
        scroll_to_track(driver, i)
        wait_until_shown(driver,"CSS_SELECTOR", '[data-testid="tracklist-row"]', 20)
        musics, covers, toto = scrapAllMusic(driver, musics, covers, thumbnail,nbr, "", isSpotify)
        
    return musics, covers

#Input : element is a WebElement containing 1 music. 
#Takes the little picture, changes the link to get the big one
def scrap_cover(driver, element):
    img_elem = element.find_element(By.TAG_NAME, "img")
    img_link = img_elem.get_attribute("src")
    img_link =  img_link[:36] + "b273" + img_link[40:]
    return img_link

#Takes in entry the string scrapped from the playlist
#Returns the string broken in this format : [numberInPlaylist, title, [artists], album, time since published, duration]
#Retire les ' pour ne pas bloquer avec le SQL
def breakit(data: str) -> list:
    lines = [line.strip() for line in data.strip().split('\n') if line.strip()]
    
    if lines[2]=="E":
        del(lines[2])
    
    index = lines[0]
    title = lines[1].replace("'", " ")
    duration = lines[-1]
    date = lines[-2]
    album = lines[3].replace("'", " ")
    artists_str = lines[2]
    
    if artists_str == "E":
        artists = []
    else:
        artists = [a.strip().replace("'", " ") for a in artists_str.split(",")]
    artists_final = []
    for el in artists:
        if el != '':
            artists_final.append(el)

    return [index, title, artists_final, album, date, duration]
#Makes a clean list of lists with breakit
#Add the link to the cover 
def extractinfo(driver, musics, cover):
    tab = []
    if cover!=None :
        for i in range(len(musics)):
            musics[i][1].append(cover[i][1])
            tab.append(musics[i][1])
    else :
        for i in range(len(musics)):
            tab.append(musics[i][1])
    return tab

def listtostring(liste):
    string = ""
    for i in liste :
        string = string + ', ' + str(i)
    return string

#Search musics on youtube music and add the domain.
#Returns the link list and the extention only (for database)
def searchMusic(musics):
    yt = YTMusic()
    final = []
    extensions = []
    for i in range(len(musics)):
        try :
            name = musics[i][1]+ " " + listtostring(musics[i][2])
            research = yt.search(name)
            
            k=0
            while research[k]['resultType'] == 'artist' or research[k]['resultType'] == 'album':
                k+=1
                try :
                    research[k]
                except :
                    research = yt.search(musics[i][1])
                    k= 0
            link = "https://music.youtube.com/watch?v=" + research[k]['videoId']
            extension = research[k]['videoId']
            print("Link found on youtube music for : ", musics[i][1] , " , ",link)
            final.append([i+1,link])
            extensions.append([i+1,extension])
        except Exception as e:
            print("Failed to locate music link : ", e)
            final.append([i+1,None])
            extensions.append([i+1,None])
    return final,extensions


def dlCover(link, identifiant):
    path = pathlib.Path(__file__).parent.resolve()
    path = str(path)
    path = path + f"/temp/{identifiant}"
    
    response = requests.get(link, stream=True)
    response.raise_for_status()
    
    with open(path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"Got the cover number {identifiant} : {path}")
    return path



#===========================================================
#===========================================================
#===========================================================
#                          DATABASE
#===========================================================
#===========================================================
#===========================================================


#crée la connection à la database
def create_connection():
    #set db_file to baseSpotify
    db_file = pathlib.Path(__file__).parent.resolve()
    db_file = str(db_file)
    db_file = db_file + "/baseSpotify"
    
    conn = None
    try:
        conn = sqlite3.connect(db_file, timeout=10)
        
        print("Found database !!")
    except Error as e:
        print(e)
        
    return conn
             
#print une colonne demandée d'une table demandée
def select_table(conn, table, column):
       select = "SELECT " + column + " FROM " + table
       cur = conn.cursor()
       cur.execute(select)
       
       rows = cur.fetchall()
       cur.close()
       for row in rows:
           print(row)
           
#Cherche les lignes où critere est commun à tous. critere est dans column lui meme dans table
def select_row_in_table(conn, table, column, critere):
    
    data = columns(conn, table, False)
    column2 = column + ", "
    data = data[:-2]
    data = data.replace(column2, "")
    critere = "'" + critere + "'"
    select = "SELECT " + data + " FROM " + table + " WHERE " + column + " = " + critere
    cur = conn.cursor()
    cur.execute(select)
    sortie = ""
    rows = cur.fetchall()
    for row in rows:
        sortie = row
    cur.close()    
    return sortie
        
#renvoie les colonnes d'une table. show est une boolean qui demande de montrer ou pas les collones
def columns(conn, table, show):
    toto = ""
    numbers = 1
    with conn:
        cur = conn.execute("SELECT * FROM " + table) 
        for column in cur.description:
            if show:
                print(numbers, ". ", column[0])
            numbers = numbers +1
            toto = toto + column[0] + ", "
    return toto

#Ferme la connection à la database
def disconnect(conn):
    try:
        conn.close()
        print("\n Disconnected successfully")
    except Error as e:
        print(e)
        
#Montre toutes les table/view de la database  
def tables(conn, types):
    cur = conn.cursor()
    select = "SELECT * FROM sqlite_master WHERE type='" + types + "';"
    cur.execute(select)
    tables_name = cur.fetchall()
    numbers = 1
    
    for table in tables_name:
        
        print(numbers, "%s"%table[1])
        numbers = numbers + 1
    cur.close()
  
#Insert une value dans la column de la table
#Si on souhaite executer directement une requette insert, on dit que isAlreadyString et on met dans request
def insert(conn, table, column, value, isAlreadyString, request):
    if isAlreadyString == 0:
        insert = "INSERT INTO " + table + " (" + column + ")VALUES ('" + value + "');"
    else:
        insert = request
    with conn :
        conn.execute(insert)
    
#Convertie une tuple en string
def convert_tuple(tup):
    string = ''
    for item in tup:
        string = string + str(item) + " "
    return string

#Transforme une string en int
def str_to_int(string):
    res=""
    digits="0123456789"
    for i in string:
        if i in digits:
            res+=i
    return res
    
#Renvoie l'ID du terme recherché dans la table recharchée
def id_finder(conn, table, column, critere, isQuery, query):
    if not isQuery:
        select = "SELECT ID FROM " + table + " WHERE " + column + "='" + critere + "';"
    else :
        select = query
    with conn :
        cur = conn.execute(select)
        rows = cur.fetchall()
    ID = ""
    for row in rows:
        ID = row
    ID_2 = convert_tuple(ID)
    ID_3 = str_to_int(ID_2)
    conn.commit()
    cur.close()
    
    return ID_3

def IdIfNotPresent(conn, table, column, value, isQuery, query):
    get_it = id_finder(conn, table, column, value, isQuery, query)
    if get_it == "":
        insert(conn, table, column, value, 0, "")
        get_it = id_finder(conn, table, column, value, isQuery, query)
        
    return get_it


#CETTE FONCTION A POUR OBJECTIF DE RÉSUMER L'AJOUT DE DONNÉES DANS LA BASE DE DONNÉE.
#NE SURTOUT PAS CHANGER SI ÇA FONCTIONNE, FONCTION TRÈS SENSIBLE

#Ajoute 1 seule musique (vérifie qu'elle n'y soit pas déja),
#regarde pour les artistes, vérifie si ils existent, pareil pour album...
#music est un tableau de la meme forme que renvoie extractInfo()
def ajoutMusique(conn, music, link):
    music_id = id_finder(conn, "music", "link", link, False, "")
    if music_id == "" : 
        #On prend tous les artists
        artists = music[2]
        artists_id = []
        #On récupère leur id
        for i in range(len(artists)):
            print("Artists = ",artists[i])
            toto = IdIfNotPresent(conn, "artist", "name", artists[i], False, "")
            print("Artist_id : ", toto)
            artists_id.append(toto)
        #On prend l'album
        album_id = 0
        album_id = IdIfNotPresent(conn, "album", "name, artist", music[3] + "', '"  + artists_id[0], True, "SELECT ID FROM album WHERE name = '"+music[3]+"' AND artist = '"+ str(artists_id[0]) + "'")
        #On crée la musique nouvelle
        #print("album id vaut : ", album_id[0])
        insert(conn, "music", "title, link, album", music[1]+ "', '" + link + "', '" + str(album_id[0]) , 0, "")
        #On réccupère son identifiant
        music_id = id_finder(conn, "music", "title", music[1], False, "")
        for i in artists_id:
            #On relie les artistes et la musique
            insert(conn, "lienartistmusic", "music_id, artist_id", str(music_id[0]) +"," + str(i), 1, "INSERT INTO lienartistmusic (music_id, artist_id) VALUES (" + music_id + ", " + i + ");")
            conn.commit()
        music[0] = music_id
        return music
        
        
    else :
        print(music[1], " est déja présente dans la base")
        return None


#===========================================================
#===========================================================
#===========================================================
#                     YOUTUBE MUSIC
#===========================================================
#===========================================================
#===========================================================




def yt_dl(musics):
    #Boucle car plusieurs liens dans plusieurs dossiers /!\ musics[i] est une liste
    for i in range(len(musics)-1):
        #Crée le dossier s'il n'existe pas 
        os.makedirs("albums/" + musics[i][3], exist_ok=True)
        #Options d'installation
        #outtmpl : dossier de sortie + titre 
        #Remote_components :
        #interval : reproduit le comportement humain pour anti-bot
        #extracor args : 
            #Change de client pour éviter les antibots et pouvoir installer un grand nombre de musiques dans erreur
        #Post processors : parametres externes (les --() dans l'invite de comande)
            #key : extractAudio = pas de video 
            #preferredcodec : format de l'audio 
            #key embedthumbnail : Demande une couverture
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': f'{"albums/" + musics[i][3]}/{musics[i][1]}.%(ext)s',
            "sleep_interval": 2,
            "max_sleep_interval": 5,
            "retries": 10,
            "ignoreerrors": True,

            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                },
                {
                    'key': 'FFmpegMetadata',  
                    'add_metadata': True,
                },
                {
                    'key': 'MetadataFromField',  
                    'formats': [
                        #f'artist:{musics[i][2][0]}',
                        #f'album:{musics[i][3]}',
                        #f'title:{musics[i][1]}',
                        f'artist:{musics[i][2][0]}',
                        f'album:{musics[i][3]}',
                        f'title:{musics[i][1]}',
                    ]
                },
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                },
                {
                    "key": "EmbedThumbnail",
                }
            ],

            # Overrides the thumbnail with your local file
            'thumbnailsconvertor': False,
            'writethumbnail': False,        # don't fetch YouTube thumbnail
            'convert_thumbnail': False,
            '__postprocessor_hooks': [],
        }
            
        
        #En utilisant les options ydl_opts, installer les musiques.
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            """info = ydl.extract_info(musics[i][7], download=True)
            info['thumbnails'] = [{'filepath': "temp/" + musics[i][0], 'id': 'local', 'url' : ''}]
            ydl.post_process(info['requested_downloads'][0]['filepath'], info)
            #ydl.download(musics[i][7])"""
            thumbnail_path = os.path.abspath("temp/" + musics[i][0])
    
            info = ydl.extract_info(musics[i][7], download=True)
            info['thumbnails'] = [{'filepath': thumbnail_path, 'id': 'local', 'url': ''}]
            info.setdefault('__files_to_move', {})[thumbnail_path] = thumbnail_path
            files_to_move = {thumbnail_path: thumbnail_path}

            
            ydl.post_process(info['requested_downloads'][0]['filepath'], info, files_to_move)


#===========================================================
#===========================================================
#===========================================================
#                        EXECUTION
#===========================================================
#===========================================================
#===========================================================



#Extract all from spotify
#=====================================
"""
playlist = "https://open.spotify.com/playlist/7gxLKaI7Ta1Rql8VQfDlYi"
playlist = "https://open.spotify.com/playlist/37i9dQZF1DXbS5WTN5nKF7" 
#playlist = "https://open.spotify.com/album/0owIvIFEbUN6xtsplJHOjZ"
driver = select_browser("Firefox")

open_playlist(driver, playlist)
#time.sleep(40)
print(getInfo(driver, playlist))

musics, covers = scrap_playlist(driver, playlist, True)
#time.sleep(1)
#print("On est musique 34")
#scroll_to_track(driver, 34)
final = extractinfo(driver, musics, covers)

youtubeLinks, extensions = searchMusic(final)

driver.quit()
"""
#====================================

#Database adding and searching
#====================================

final = [['1', 'Save Me Tonight', ['Jennifer Lopez', 'David Guetta'], 'Save Me Tonight', '5 days ago', '3:16', 'https://i.scdn.co/image/ab67616d0000b273ab06fe415d821163f1372f75'], ['2', 'What You Want', ['Angèle', 'Justice'], 'What You Want', '5 days ago', '3:08', 'https://i.scdn.co/image/ab67616d0000b273dead0548b222459aa1a27ef9'], ['3', 'I Just Might', ['Bruno Mars'], 'I Just Might', '5 days ago', '3:32', 'https://i.scdn.co/image/ab67616d0000b273e7623a0a60f330ee2b24d498'], ['4', 'Comme Caroline (feat. MC Solaar)', ['Zaho', 'MC Solaar'], 'Comme Caroline (feat. MC Solaar)', '5 days ago', '3:05', 'https://i.scdn.co/image/ab67616d0000b273aefe81e4291584c4c5986b29'], ['5', 'FEVER DREAM', ['Alex Warren'], 'FEVER DREAM', '5 days ago', '2:33', 'https://i.scdn.co/image/ab67616d0000b273e98fb90ec2e15c005a0b6f7f'], ['6', 'Dracula - JENNIE Remix', ['Tame Impala', 'JENNIE'], 'Dracula (Remix)', '5 days ago', '3:29', 'https://i.scdn.co/image/ab67616d0000b273c7c031ce9d06b131f8563676'], ['7', 'New Religion', ['Bebe Rexha', 'Faithless'], 'New Religion', '5 days ago', '2:54', 'https://i.scdn.co/image/ab67616d0000b2731b032b989cb6d28908bde1c6'], ['8', 'Soirée mondaine', ['Oria'], 'Soirée mondaine', '5 days ago', '3:18', 'https://i.scdn.co/image/ab67616d0000b273d3d724135dfa21b31b962a58'], ['9', 'Dream As One - from Avatar: Fire and Ash', ['Miley Cyrus'], 'Dream As One (from Avatar: Fire and Ash)', '5 days ago', '3:19', 'https://i.scdn.co/image/ab67616d0000b273b639fbb0e736245d83407141'], ['10', 'melodrama', ['disiz', 'Theodora'], 'melodrama', '5 days ago', '2:56', 'https://i.scdn.co/image/ab67616d0000b273ee5f01b81fd02d6b2dbd70c5'], ['11', 'Opalite', ['Taylor Swift'], 'The Life of a Showgirl', '5 days ago', '3:55', 'https://i.scdn.co/image/ab67616d0000b273d7812467811a7da6e6a44902'], ['12', 'La recette', ['Jeck', 'Carla'], 'Oxygène', '5 days ago', '3:02', 'https://i.scdn.co/image/ab67616d0000b273d68b074e561631ca7cfacdca'], ['13', 'End of Beginning', ['Djo'], 'End of Beginning', '5 days ago', '2:39', 'https://i.scdn.co/image/ab67616d0000b273b06eabf1f19c0e82c5e82029'], ['14', 'Ça fait mal', ['Vitaa'], 'Charlotte', '5 days ago', '3:09', 'https://i.scdn.co/image/ab67616d0000b273ec5c8534506b7fb67c36a220'], ['15', 'Drive Safe', ['Myles Smith', 'Niall Horan'], 'Drive Safe', '5 days ago', '3:21', 'https://i.scdn.co/image/ab67616d0000b2736cfdc33ea599e7441055f444'], ['16', 'La lune', ['Christophe Maé'], 'La lune', '5 days ago', '3:28', 'https://i.scdn.co/image/ab67616d0000b2738dee671f67d2216f5b708d4a'], ['17', 'Gone Gone Gone', ['David Guetta', 'Teddy Swims', 'Tones And I'], 'Gone Gone Gone', '5 days ago', '3:18', 'https://i.scdn.co/image/ab67616d0000b273b89fa8e4480031eb17c2bf4f'], ['18', 'Zoo', ['Disney', 'Shakira'], 'Zootopie 2 (Bande Originale du Film)', '5 days ago', '3:10', 'https://i.scdn.co/image/ab67616d0000b27391d5acc78d65f39ab8259b07'], ['19', 'ONE TRACK MIND', ['Naïka'], 'ONE TRACK MIND', '5 days ago', '3:20', 'https://i.scdn.co/image/ab67616d0000b273512f0cf488a7ca0837b57dbd'], ['20', 'Quand même', ['M. Pokora'], 'Adrénaline', '5 days ago', '3:13', 'https://i.scdn.co/image/ab67616d0000b273bb40200218a04f3d9c4aebd1'], ['21', 'Homewrecker', ['sombr'], 'Homewrecker', '5 days ago', '3:29', 'https://i.scdn.co/image/ab67616d0000b2739a8d41dca4c7d0ef23d76dd7'], ['22', 'WHERE IS MY HUSBAND!', ['RAYE'], 'WHERE IS MY HUSBAND!', '5 days ago', '3:17', 'https://i.scdn.co/image/ab67616d0000b2736ac3c7938191585c53c8180d'], ['23', 'Tant pis pour elle', ['Charlotte Cardin'], 'Tant pis pour elle', '5 days ago', '2:38', 'https://i.scdn.co/image/ab67616d0000b2730fef5bdfcbe88a74f734523a'], ['24', 'Elizabeth Taylor', ['Taylor Swift'], 'The Life of a Showgirl', '5 days ago', '3:28', 'https://i.scdn.co/image/ab67616d0000b273d7812467811a7da6e6a44902'], ['25', 'Mr. Know It All', ['Teddy Swims'], 'Mr. Know It All', '5 days ago', '3:18', 'https://i.scdn.co/image/ab67616d0000b273ecf61285415fd9c2a3f7d384'], ['26', 'ça pik un peu quand même', ['miki'], 'industry plant', '5 days ago', '2:17', 'https://i.scdn.co/image/ab67616d0000b273ba8be36b58e5d17d9fe621d9'], ['27', 'Die On This Hill', ['SIENNA SPIRO'], 'Die On This Hill', '5 days ago', '3:37', 'https://i.scdn.co/image/ab67616d0000b273ec4833919808083d733ca9af'], ['28', 'Frérot', ['Jérémy Frerot'], 'Gamin des sables', '5 days ago', '2:43', 'https://i.scdn.co/image/ab67616d0000b273034d8f09aac2d14cd1f6ad9e'], ['29', 'ALGO TÚ', ['Shakira', 'Beéle'], 'ALGO TÚ', '5 days ago', '3:33', 'https://i.scdn.co/image/ab67616d0000b273e938517baf9bd13b8ba72455'], ['30', 'Je pense à vous', ['Pierre de Maere'], 'Je pense à vous', '5 days ago', '2:52', 'https://i.scdn.co/image/ab67616d0000b273fe0f4630205398653e6074df'], ['31', 'The First Time', ['Damiano David'], 'FUNNY little FEARS', '5 days ago', '3:38', 'https://i.scdn.co/image/ab67616d0000b273cd84a8be0da1523554f5dd5e'], ['32', 'Soleil', ['GIMS'], 'Soleil', '5 days ago', '2:11', 'https://i.scdn.co/image/ab67616d0000b273da7027e8cccc2cc011fdd078'], ['33', 'Gabriela', ['KATSEYE'], 'Gabriela', '5 days ago', '3:17', 'https://i.scdn.co/image/ab67616d0000b273f8d4d00ffe09373efb13ce29'], ['34', 'Camera', ['Ed Sheeran'], 'Play', '5 days ago', '3:35', 'https://i.scdn.co/image/ab67616d0000b273b07c28bb3192bdfb585fb438'], ['35', 'The Fate of Ophelia', ['Taylor Swift'], 'The Life of a Showgirl', '5 days ago', '3:46', 'https://i.scdn.co/image/ab67616d0000b273d7812467811a7da6e6a44902'], ['36', 'OK KO (feat. Kyo)', ['Superbus', 'Kyo'], 'OK KO (Nouvelle Édition)', '5 days ago', '2:46', 'https://i.scdn.co/image/ab67616d0000b273e77e444ec0f210c035860c3a'], ['37', 'Almost', ['Lewis Capaldi'], 'Survive - EP', '5 days ago', '3:40', 'https://i.scdn.co/image/ab67616d0000b2739d07ee7633e8e1b81fc2a9a9'], ['38', 'Dis-moi où (feat. OTTA)', ['Julien Lieb', 'OTTA'], 'Naufragé', '5 days ago', '2:41', 'https://i.scdn.co/image/ab67616d0000b273f25909b3e6ae31125e798962'], ['39', 'American Girls', ['Harry Styles'], 'Kiss All The Time. Disco, Occasionally.', '5 days ago', '3:33', 'https://i.scdn.co/image/ab67616d0000b27374959140f550b11049c18a38'], ['40', 'Le Petit Pêcheur', ['Manon Lisa'], 'Le Petit Pêcheur', '5 days ago', '2:09', 'https://i.scdn.co/image/ab67616d0000b2733d89535c1ff6c4c0e3ff61e9'], ['41', 'silent treatment', ['Freya Skye'], 'stardust', '5 days ago', '2:22', 'https://i.scdn.co/image/ab67616d0000b273b1dca715942a5394f43b256e'], ['42', 'GIRLFRIEND', ['Tayc'], 'GIRLFRIEND', '5 days ago', '4:19', 'https://i.scdn.co/image/ab67616d0000b27381334f76140b3936d0605acd'], ['43', 'Free', ['Rumi', 'Jinu', 'KPop Demon Hunters Cast', 'EJAE'], 'KPop Demon Hunters (Soundtrack from the Netflix Film)', '5 days ago', '3:07', 'https://i.scdn.co/image/ab67616d0000b2734dcb6c5df15cf74596ab25a4'], ['44', 'L horizon', ['Pierre Garnier'], 'Chaque seconde', '5 days ago', '2:42', 'https://i.scdn.co/image/ab67616d0000b27349b57472dfa8359df0f0d8c2'], ['45', 'Turn The Lights Off - Radio Edit', ['Kato', 'Jon'], 'Turn The Lights Off', '5 days ago', '2:58', 'https://i.scdn.co/image/ab67616d0000b273b709bed32c87dadd3163d892'], ['46', 'L amour ça se donne', ['Amel Bent'], 'L amour ça se donne', '5 days ago', '2:46', 'https://i.scdn.co/image/ab67616d0000b2735ebb19d703eb63ad02a3e486'], ['47', 'Madan', ['Trinix', 'Thanda Choir'], 'Madan', '5 days ago', '2:25', 'https://i.scdn.co/image/ab67616d0000b273adaaf53d902d1579e349449e'], ['48', 'Qu est-ce qu il me restera ?', ['Claudio Capéo'], 'Nouveau souffle', '5 days ago', '2:22', 'https://i.scdn.co/image/ab67616d0000b273ae8f0b84ce417960bbdd84bd'], ['49', 'WE ARE GOOD', ['Skip the Use'], 'WE ARE GOOD', '5 days ago', '2:16', 'https://i.scdn.co/image/ab67616d0000b2734a3a2e632e38abe4e3d6cb5d'], ['50', 'La Camisa Negra', ['Elliott'], 'La Camisa Negra', '5 days ago', '2:39', 'https://i.scdn.co/image/ab67616d0000b273e848f6206d7056abe8b889f4']]
extensions = [[1, 'y8HLQn3YAiw'], [2, 'e5s8MdtnbMM'], [3, 'mrV8kK5t0V8'], [4, 'uRA8xnBxm8U'], [5, 'hkUSnrHQJHg'], [6, '0UPDBODtxzw'], [7, '366CV87TguE'], [8, 'xzBTvODwmr8'], [9, '6rrSeNLcsTE'], [10, 'll5uAeEanjY'], [11, '1FVF-9KQiPo'], [12, '9kBpbQDZdbQ'], [13, 'oXSw8DGjf5E'], [14, '3SoSpZTcxVo'], [15, 'mzy9u2DKWxc'], [16, 'CM2D0LoSGU0'], [17, '8iT9DRe3cHE'], [18, 'Kw3935PH01E'], [19, 'PhxPYdBRgYs'], [20, 'Hl2Z6P74URo'], [21, 'mQezde_qeXw'], [22, 'rK5TyISxZ_M'], [23, 'Eg4hjfjS0YQ'], [24, '7X5iDKPrZH0'], [25, 'KllnaNOxe0I'], [26, 's1At5s0YLSs'], [27, 'pxC9NhXv_1M'], [28, 'RTrZtuLe5zI'], [29, 'mXz8F1Yjy9I'], [30, 'kb3VccFdBpw'], [31, 'n1Hzf_is8tI'], [32, 'QAJGWSM6Z-w'], [33, 'co-TFLbaZAE'], [34, 'O8WXFI_MSAI'], [35, 'ko70cExuzZM'], [36, 's5_FeVBGQ4w'], [37, 'NVS8K4K_MD0'], [38, 'axHJd_KxiQk'], [39, 'o6jQo3-iCao'], [40, 'mOUdsRP41qY'], [41, '6aLOWIPVE9g'], [42, 'K9anmn5pgxw'], [43, '-ymi6hZahlo'], [44, 'fj_MkTfWS3s'], [45, 'FxDMMeWK1ZE'], [46, '2p6w2i0T3oE'], [47, 'R-Vjsl95Vok'], [48, '9Y3y7eHerFU'], [49, 'tdVSHT9zvmU'], [50, 'NEmqFapidDs']]
youtubeLinks = [[1, 'https://music.youtube.com/watch?v=y8HLQn3YAiw'], [2, 'https://music.youtube.com/watch?v=e5s8MdtnbMM'], [3, 'https://music.youtube.com/watch?v=mrV8kK5t0V8'], [4, 'https://music.youtube.com/watch?v=uRA8xnBxm8U'], [5, 'https://music.youtube.com/watch?v=hkUSnrHQJHg'], [6, 'https://music.youtube.com/watch?v=0UPDBODtxzw'], [7, 'https://music.youtube.com/watch?v=366CV87TguE'], [8, 'https://music.youtube.com/watch?v=xzBTvODwmr8'], [9, 'https://music.youtube.com/watch?v=6rrSeNLcsTE'], [10, 'https://music.youtube.com/watch?v=ll5uAeEanjY'], [11, 'https://music.youtube.com/watch?v=1FVF-9KQiPo'], [12, 'https://music.youtube.com/watch?v=9kBpbQDZdbQ'], [13, 'https://music.youtube.com/watch?v=oXSw8DGjf5E'], [14, 'https://music.youtube.com/watch?v=3SoSpZTcxVo'], [15, 'https://music.youtube.com/watch?v=mzy9u2DKWxc'], [16, 'https://music.youtube.com/watch?v=CM2D0LoSGU0'], [17, 'https://music.youtube.com/watch?v=8iT9DRe3cHE'], [18, 'https://music.youtube.com/watch?v=Kw3935PH01E'], [19, 'https://music.youtube.com/watch?v=PhxPYdBRgYs'], [20, 'https://music.youtube.com/watch?v=Hl2Z6P74URo'], [21, 'https://music.youtube.com/watch?v=mQezde_qeXw'], [22, 'https://music.youtube.com/watch?v=rK5TyISxZ_M'], [23, 'https://music.youtube.com/watch?v=Eg4hjfjS0YQ'], [24, 'https://music.youtube.com/watch?v=7X5iDKPrZH0'], [25, 'https://music.youtube.com/watch?v=KllnaNOxe0I'], [26, 'https://music.youtube.com/watch?v=s1At5s0YLSs'], [27, 'https://music.youtube.com/watch?v=pxC9NhXv_1M'], [28, 'https://music.youtube.com/watch?v=RTrZtuLe5zI'], [29, 'https://music.youtube.com/watch?v=mXz8F1Yjy9I'], [30, 'https://music.youtube.com/watch?v=kb3VccFdBpw'], [31, 'https://music.youtube.com/watch?v=n1Hzf_is8tI'], [32, 'https://music.youtube.com/watch?v=QAJGWSM6Z-w'], [33, 'https://music.youtube.com/watch?v=co-TFLbaZAE'], [34, 'https://music.youtube.com/watch?v=O8WXFI_MSAI'], [35, 'https://music.youtube.com/watch?v=ko70cExuzZM'], [36, 'https://music.youtube.com/watch?v=s5_FeVBGQ4w'], [37, 'https://music.youtube.com/watch?v=NVS8K4K_MD0'], [38, 'https://music.youtube.com/watch?v=axHJd_KxiQk'], [39, 'https://music.youtube.com/watch?v=o6jQo3-iCao'], [40, 'https://music.youtube.com/watch?v=mOUdsRP41qY'], [41, 'https://music.youtube.com/watch?v=6aLOWIPVE9g'], [42, 'https://music.youtube.com/watch?v=K9anmn5pgxw'], [43, 'https://music.youtube.com/watch?v=-ymi6hZahlo'], [44, 'https://music.youtube.com/watch?v=fj_MkTfWS3s'], [45, 'https://music.youtube.com/watch?v=FxDMMeWK1ZE'], [46, 'https://music.youtube.com/watch?v=2p6w2i0T3oE'], [47, 'https://music.youtube.com/watch?v=R-Vjsl95Vok'], [48, 'https://music.youtube.com/watch?v=9Y3y7eHerFU'], [49, 'https://music.youtube.com/watch?v=tdVSHT9zvmU'], [50, 'https://music.youtube.com/watch?v=NEmqFapidDs']]
temp_path = str(pathlib.Path(__file__).parent.resolve()) + "/temp/"


conn = create_connection()

print(tables(conn, "table"))

for i in range(len(final)):
    final[i].append(youtubeLinks[i][1])

#i=12
toDl = []
for i in range(len(final)):
    if extensions[i][1] != None:
        musique = ajoutMusique(conn, final[i], extensions[i][1])
    if musique != None:
        toDl.append(musique)

#toDl = [['11', 'La recette', ['Jeck', 'Carla'], 'Oxygène', '3 days ago', '3:02', 'https://music.youtube.com/watch?v=9kBpbQDZdbQ', 'https://i.scdn.co/image/ab67616d00001e02d68b074e561631ca7cfacdca']]


print("\n\n\n")
#Remplacer les 1er 0 par des i pour grande échelle
for i in range(len(toDl)):
    dlCover(toDl[i][6], toDl[i][0])
    while not os.path.exists(temp_path):
        time.sleep(0.1)
if toDl != []:
    yt_dl(toDl)


#disconnect(conn)
#====================================