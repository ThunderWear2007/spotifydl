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
import re
from yt_dlp.postprocessor import FFmpegThumbnailsConvertorPP, EmbedThumbnailPP

 
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
def extract_nbr(text):
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
def get_info(driver, link):
    nbr = 0 
    isSpotify = False
    try :
        wait_until_shown(driver,"CLASS", "jQEzizWq_N0wiIS3", 20)
        element_nbr = driver.find_element(By.CLASS_NAME, "jQEzizWq_N0wiIS3")
        try:
            playlist_name = driver.find_element(By.CSS_SELECTOR, '[data-testid="entityTitle"]')
        except:
            print('No name found for this playlist')
        try :
            driver.find_element(By.CLASS_NAME, "lBNjRAMrqbOebmsh")
        except : 
            print("Playlist from Spotify")
            isSpotify = True
        
        nbr = extract_nbr(element_nbr.text)
    except Exception as e :
        print("Failed :", e)
    return nbr, isSpotify, playlist_name.text

#Gets all of the musics id of the missing ones in the list musics
def get_missing(musics):
    total = []
    for i in range(len(musics)):
        if musics[i][1] == None :
            total.append(i)
    return total


#Scroll jusqu'à la musique numéro track_index
def scroll_to_track(driver, track_index: int):
    driver.execute_script("""const container = document.querySelectorAll("[data-overlayscrollbars-viewport]")[1];container.scrollTop = arguments[0] * 56;""", track_index)


#Scrap all the music on the page, to call in a while loop with end condition
def scrap_all_music(driver, musics, covers, thumbnail, nbr, end, isSpotify):
    elements, elements_text, elements_number = [],[],[]
    try :
        elements = []
        wait_until_shown(driver,"CSS_SELECTOR", '[data-testid="tracklist-row"]', 20)
        elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tracklist-row"]')
        elements_text = [el.text for el in elements]
        elements_number = []
        for el in elements_text:
            try:
                order = extract_nbr(el)
                elements_number.append(order)
            except:
                None
                
        for j in range(len(elements)):
            songNbrinPlaylist = elements_number[j]
            if musics[songNbrinPlaylist-1][1] == None:
                musics[songNbrinPlaylist-1][1] = break_it(elements[j])
                try:
                    covers[songNbrinPlaylist-1][1] = scrap_cover(driver, elements[j])
                    album_link = scrap_album(driver, elements[j])
                except StaleElementReferenceException:
                    # Full re-fetch, restart from scratch
                    return scrap_all_music(driver, musics, covers, thumbnail, nbr, end, isSpotify)
                    
        if songNbrinPlaylist == nbr:
            end = True
                
        if end == False or end == True:
            scroll_to_track(driver, elements_number[-6])
        
    except Exception as e: 
        print("\n \nERROR scrap_all_music  \n", e)
        #end = True
        if e == "invalid literal for int() with base 10: ''":
            print("regarde !")
    
    return musics,covers,end
        


#With the playlist, scrap all the musics. Returns a list containing all the musics name, artist, album & duration    
def scrap_playlist(driver, link, thumbnail):
    end = False
    nbr, isSpotify, name = get_info(driver, link)
    musics = [None]*nbr
    covers = [None]*nbr
    for i in range(nbr):
        musics[i]=[i, None]
        covers[i]=[i, None]
    
    while not end:
        musics, covers, end = scrap_all_music(driver, musics, covers, thumbnail, nbr, end, isSpotify)
        
    missing_id = get_missing(musics)
    print(missing_id)
    for i in missing_id:
        scroll_to_track(driver, i)
        wait_until_shown(driver,"CSS_SELECTOR", '[data-testid="tracklist-row"]', 20)
        musics, covers, toto = scrap_all_music(driver, musics, covers, thumbnail,nbr, "", isSpotify)
        
    return musics, covers, name

#Input : element is a WebElement containing 1 music. 
#Takes the little picture, changes the link to get the big one
def scrap_cover(driver, element):
    img_elem = element.find_element(By.TAG_NAME, "img")
    img_link = img_elem.get_attribute("src")
    img_link =  img_link[:36] + "b273" + img_link[40:]
    return img_link

def scrap_album(driver, element):
    album = element.find_element(By.CLASS_NAME, "F_VvNCRKZ2cKj1a9")
    print(album.tag_name)
    album_link = album.get_attribute("href")
    album_link = album_link[:7]
    return album_link
    

#Takes in entry the string scrapped from the playlist
#Returns the string broken in this format : [numberInPlaylist, title, [artists], album, time since published, duration]
#Retire les ' pour ne pas bloquer avec le SQL
def break_it(element):
    artists_element = element.find_elements(By.CLASS_NAME, "HyipfPVwSpodPBHR")
    
    artists_final = [el.text for el in artists_element[0].find_elements(By.CSS_SELECTOR, '[tabindex="-1"]')]
    
    data = element.text
    lines = [line.strip() for line in data.strip().split('\n') if line.strip()]
    index = lines[0]
    
    if index == '66':
        None
    for i in range(len(artists_final)):
        artists_final[i] = re.sub("'", " ", artists_final[i])

    title = lines[1].replace("'", " ")
    duration = lines[-1]
    date = lines[-2]
    album = lines[3].replace("'", " ")

    return [index, title, artists_final, album, date, duration]

#Makes a clean list of lists with break_it
#Add the link to the cover 
def add_links(driver, musics, cover):
    tab = []
    if cover!=None :
        for i in range(len(musics)):
            musics[i][1].append(cover[i][1])
            tab.append(musics[i][1])
    else :
        for i in range(len(musics)):
            tab.append(musics[i][1])
    return tab

#Converts a list into a string with each element separated by a comma
def list_to_string(liste):
    string = ""
    for i in liste :
        string = string + ', ' + str(i)
    return string

#Search musics on youtube music and add the domain.
#Returns the link list and the extention only (for database)
def search_music(conn, musics):
    yt = YTMusic()
    #final = [None]*len(musics)
    final = []
    extensions = []
    """for i in range(len(musics)):
        final[i]=[i+1, None]"""
    ids = []
    for i in range(len(musics)):
        try :
            name = musics[i][1]+ " " + list_to_string(musics[i][2])
            music_id = id_finder(conn, "music", "title", musics[i][1], False, "")
            ids.append([i+1, music_id])
            if music_id == "":
                research = yt.search(name,filter="songs")
                k=0
                while research[k]['resultType'] == 'artist' or research[k]['resultType'] == 'album':
                    k+=1
                    try :
                        research[k]
                    except :
                        print(f'research failed for {musics[i][1]} : {research[k-1]['resultType']}')
                        research = yt.search(musics[i][1] + "song", filter="songs")
                        k= 0
                link = "https://music.youtube.com/watch?v=" + research[k]['videoId']
                extension = research[k]['videoId']
                print("Link found on youtube music for : ", musics[i][1] , " , ",link)
                #final[i][1] =  link
                final.append([i+1, link])
                extensions.append([i+1,extension])
        except Exception as e:
            print("Failed to locate music link : ", e)
            final.append([i+1,None])
            extensions.append([i+1,None])
    return final,extensions, ids


#Dowloads the cover from the link with the name of the id of the music
def dl_cover(link, identifiant):
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

#Combines all operations of all precedent function to have a clean output, the links, and the name of the playlist
def scrap(conn, playlist):
    driver = select_browser("Firefox")
    open_playlist(driver, playlist)
    input("Est-ce le bon lien ?")
    print(f'There is {get_info(driver, playlist)} songs in this playlist')
    musics, covers, name = scrap_playlist(driver, playlist, True)
    driver.quit()
    final = add_links(driver, musics, covers)
    youtubeLinks, extensions, ids = search_music(conn, final)
    return final, youtubeLinks, extensions, name, ids

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
    final = []
    for table in tables_name:
        final.append(table[1])
        print(numbers, "%s"%table[1])
        numbers = numbers + 1
    cur.close()
    return final

  
#Insert une value dans la column de la table
#Si on souhaite executer directement une requette insert, on dit que isAlreadyString et on met dans request
def insert(conn, table, column, value, isAlreadyString, request):
    if isAlreadyString == 0:
        query = "INSERT INTO " + table + " (" + column + ")VALUES ('" + value + "');"
    else:
        query = request
    with conn :
        conn.execute(query)
    
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

#Returns the id of an element, adds it if its not present already
def id_if_not_present(conn, table, column, value, isQuery, query):
    get_it = id_finder(conn, table, column, value, isQuery, query)
    if get_it == "":
        insert(conn, table, column, value, 0, "")
        get_it = id_finder(conn, table, column, value, isQuery, query)
        
    return get_it

def break_cover_link(cover_link):
    return cover_link[24:]



#CETTE FONCTION A POUR OBJECTIF DE RÉSUMER L'AJOUT DE DONNÉES DANS LA BASE DE DONNÉE.
#NE SURTOUT PAS CHANGER SI ÇA FONCTIONNE, FONCTION TRÈS SENSIBLE

#Ajoute 1 seule musique (vérifie qu'elle n'y soit pas déja),
#regarde pour les artistes, vérifie si ils existent, pareil pour album...
#music est un tableau de la meme forme que renvoie add_links()
def add_music(conn, music, link):
    music_id = id_finder(conn, "music", "music_link", link, False, "")
    if music_id == "" : 
        #On prend tous les artists
        artists = music[2]
        artists_id = []
        #On récupère leur id
        for i in range(len(artists)):
            toto = id_if_not_present(conn, "artist", "name", artists[i], False, "")
            artists_id.append(toto)
        #On prend l'album
        album_id = 0
        album_id = id_if_not_present(conn, "album", "name, artist", music[3] + "', '"  + artists_id[0], True, "SELECT ID FROM album WHERE name = '"+music[3]+"' AND artist = '"+ str(artists_id[0]) + "'")
        #On crée la musique nouvelle
        insert(conn, "music", "title, music_link, album, cover_link", music[1]+ "', '" + link + "', '" + str(album_id) + "', '" + break_cover_link(music[6]) , 0, "")
        #On réccupère son identifiant
        music_id = id_finder(conn, "music", "title", music[1], False, "")
        for i in artists_id:
            #On relie les artistes et la musique
            insert(conn, "lienartistmusic", "music_id, artist_id", str(music_id[0]) +"," + str(i), 1, "INSERT INTO lienartistmusic (music_id, artist_id) VALUES (" + music_id + ", " + i + ");")
            conn.commit()
        music[0] = music_id
        return music, music_id
        
        
    else :
        print(music[1], " est déja présente dans la base")
        return None, music_id
    
#Create a table with the name of the playlist with the music id and who added it into the playlist
def create_playlist(conn, name):
    query = 'CREATE TABLE "'+ name + '" ("music_id" INTEGER UNIQUE, "added_by" INTEGER, 	FOREIGN KEY("music_id") REFERENCES "music"("id"), FOREIGN KEY("added_by") REFERENCES "people"("id"));'
    with conn:
        try :
            conn.execute(query)
        except Exception as e :
            print(f'Failed adding playlist into database: {e}')

#Function to download only the music not already present into the database
def dl_only_musics(final, youtubeLinks, extensions):
    temp_path = str(pathlib.Path(__file__).parent.resolve()) + "/temp/"
    ids = []
    k=0
    for link in youtubeLinks:
        final[link[0]-1].append(link[1])
        if extensions[k][1] != None:
            musique, musique_id = add_music(conn, final[link[0]-1], extensions[k][1])
            ids.append(musique_id)
            if musique != None:
                dl_cover(musique[6], musique[0])
                while not os.path.exists(temp_path):
                    time.sleep(0.1)
                yt_dl(musique)
        k+=1
    return ids

#renvoie les colonnes d'une table. show est une boolean qui demande de montrer ou pas les collones
def columns(conn, table, show):
    cur = conn.cursor()
    toto = ""
    numbers = 1
    data = cur.execute("SELECT * FROM " + table) 
    for column in data.description:
        if show:
            print(numbers, ". ", column[0])
        numbers = numbers +1
        toto = toto + column[0] + ", "
    return toto

#Cherche les lignes où critere est commun à tous. critere est dans column lui meme dans table si specified
def select_row_in_table(conn, table, searching_in, critere, data, specified):
    critere = "'" + str(critere) + "'"
    if specified:
        select = "SELECT "+data+" FROM " + table + " WHERE " + searching_in + " = " + critere
    else:
        select = "SELECT "+data+" FROM '" + table + "'"
    cur = conn.cursor()
    cur.execute(select)
    rows = cur.fetchall()
    return rows

#Return all of the id in a table
def get_all_id(conn, table):
    query = "SELECT id FROM " + table
    with conn:
        result = conn.execute(query)
        final = []
        for toto in result:
            final.append(toto[0])
    return final

#Adds a list of musics to one playlist
def add_to_playlist(playlist, ids, who):
    for i in range(len(ids)):
        try : 
            insert(conn, "'" + playlist + "'", "music_id, added_by", ids[i][1] + "','" +  who, 0, "")
        except Exception as e:
            print(f'Problem importing music : {e}')


#Verifies if every music in the database is present in the folder
def check_database(conn):
    artists_id = get_all_id(conn, "artist")
    base_path = str(pathlib.Path(__file__).parent.resolve()) + "/artists/"
    unexisting_musics = []
    unexisting_albums = []
    unexisting_artists = []
    for artist in artists_id:
        albums_id = select_row_in_table(conn, "album", "artist", artist, "id", True)
        albums_name = select_row_in_table(conn, "album", "artist", artist, "name", True)
        artist_name = select_row_in_table(conn, "artist", "id", artist, "name", True)
        for i in range(len(albums_id)):
            musics_id = select_row_in_table(conn, "music", "album", albums_id[i][0], "id", True)
            musics_name = select_row_in_table(conn, "music", "album", albums_id[i][0], "title", True)
            for j in range(len(musics_name)):
                artist_path = base_path + artist_name[0][0]
                album_path = artist_path + "/"+ albums_name[i][0]
                music_path = album_path + "/" + musics_name[j][0] + ".m4a"
                artist_file_existence = os.path.exists(artist_path)
                album_file_existence = os.path.exists(album_path)
                music_file_existence = os.path.exists(music_path)
                if artist_file_existence:
                    if album_file_existence:
                        #print("Album "+ musics_name[j][0] + " exists")
                        if music_file_existence:
                            None
                            #print("Album "+ albums_name[i][0] + " exists")
                        else:
                            print("/! Music "+ musics_name[j][0] + " does not exists /! ")
                            unexisting_musics.append([musics_id[j][0], music_path])
                    else:
                        print("/! Album "+ albums_name[i][0] + " does not exists /! ")
                        unexisting_albums.append([albums_id[i][0], album_path])
                else:
                    print("/! Artist "+ artist_name[0][0] + " does not exists /! ")
                    unexisting_artists.append([artist, artist_path])
            
    return unexisting_musics, unexisting_albums

#Updates a value of a certain column 
def update(conn, table, column, value, condition):
    query = "UPDATE "+table+" SET " + column +" = '"+ value + "' WHERE "+ condition + "; "
    with conn:
        conn.execute(query)

#Changes the link of a music if its not the one 
def modify_music(conn, name, new_link):
    temp_path = str(pathlib.Path(__file__).parent.resolve()) + "/temp/"
    music_id = id_finder(conn, "music", "title", name, False, "")
    update(conn, "music", "music_link", new_link, "id =" + music_id[0])
    while not os.path.exists(temp_path):
        time.sleep(0.1)
        
    musique = extract_all_info(conn, music_id)
    dl_cover(musique[7], music_id)
    yt_dl(musique)

#Takes an id and returns the title, artist name, album name, music link & cover link with the same format taken into yt_dl
def extract_all_info(conn, music_id):
    query = "SELECT music.id, music.title, artist.name, album.name, music.music_link, music.cover_link FROM music JOIN lienartistmusic ON lienartistmusic.music_id = music.id JOIN artist ON lienartistmusic.artist_id = artist.id JOIN album ON album.id = music.album WHERE music.id = "+ str(music_id)
    with conn:
        result = conn.execute(query)
        musique_raw = result.fetchall()

    musique = [music_id ,musique_raw[0][1], [musique_raw[0][2]], musique_raw[0][3], "", "", "https://i.scdn.co/image/" +musique_raw[0][5], "https://youtube.com/watch?v=" + musique_raw[0][4]]
    return musique


#===========================================================
#===========================================================
#===========================================================
#                     YOUTUBE MUSIC
#===========================================================
#===========================================================
#===========================================================



#The function to download the music from youtube music
def yt_dl(musics):
    #Crée le dossier s'il n'existe pas 
    os.makedirs("artists/"+ musics[2][0] +"/" + musics[3], exist_ok=True)
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
        'format': 'bestaudio/best',
        'outtmpl': f'{"artists/" +musics[2][0]+"/"+ musics[3]}/{musics[1]}.%(ext)s',
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "retries": 10,
        "ignoreerrors": True,
        'remote_components': {'ejs:github'},
        #'cookiefile': '/path/to/cookies.txt',
        #'username': 'dlyoutube67@gmail.com',
        #'password': 'zX.A.tn~wYr8Y',
        #'verbose': True,

        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            },
            {
                'key': 'FFmpegMetadata',  
                'add_metadata': True,
            }
        ],
        'postprocessor_args': {
            'ffmpegmetadata': [
                '-metadata', f'artist={musics[2][0]}',
                '-metadata', f'album={musics[3]}',
                '-metadata', f'title={musics[1]}',
            ]},

        # Overrides the thumbnail with your local file
        'thumbnailsconvertor': False,
        'writethumbnail': False,        # don't fetch YouTube thumbnail
        'convert_thumbnail': False,
        '__postprocessor_hooks': [],
    }
        
    
    #En utilisant les options ydl_opts, installer les musiques.
    try: 
        with yt_dlp.YoutubeDL(ydl_opts) as ydl :
        
            thumbnail_path = os.path.abspath("temp/" + str(musics[0]))
    
            info = ydl.extract_info(musics[7], download=True)
            info['thumbnails'] = [{'filepath': thumbnail_path, 'id': 'local', 'url': ''}]
            info.setdefault('__files_to_move', {})[thumbnail_path] = thumbnail_path
            files_to_move = {thumbnail_path: thumbnail_path}
            info['ext'] = 'm4a'
            info['__postprocessors']= [FFmpegThumbnailsConvertorPP(ydl, format='jpg'),EmbedThumbnailPP(ydl)]
            ydl._pps['post_process'] = []
            ydl.post_process(info['requested_downloads'][0]['filepath'], info, files_to_move)
            print("successful")
    except :
        try:
            """for i in range(5):
                ydl_opts['cookiesfrombrowser'] = ('firefox', '/home/maxence/.mozilla/firefox/XZ6RBb1a.Profile 1', None, None)
                #ydl_opts['cookiesfrombrowser'] = ('firefox', None, None, 'XZ6RBb1a.Profile 1')
                #ydl_opts['cookiefile']  = '/home/maxence/Documents/FreeMusicClean/cookies/cookies.txt'
                print("cookiefile:", ydl_opts.get('cookiefile'))
                with yt_dlp.YoutubeDL(ydl_opts) as ydl :
                    thumbnail_path = os.path.abspath("temp/" + str(musics[0]))
                    info = ydl.extract_info(musics[7], download=True)
                    info['thumbnails'] = [{'filepath': thumbnail_path, 'id': 'local', 'url': ''}]
                    info.setdefault('__files_to_move', {})[thumbnail_path] = thumbnail_path
                    files_to_move = {thumbnail_path: thumbnail_path}
                    ydl.post_process(info['requested_downloads'][0]['filepath'], info, files_to_move)
                    break"""
        except Exception as e:
            print(e)


#===========================================================
#===========================================================
#===========================================================
#                    PLAYLIST EXPORT
#===========================================================
#===========================================================
#===========================================================

#Creates a .m3u file compatible with samsung music and my phone
def export_to_samsung_music(conn, playlist_name):
    playlist_path = str(pathlib.Path(__file__).parent.resolve()) + "/" + str(playlist_name) + ".txt"
    content = select_row_in_table(conn, playlist_name, "", "", "music_id", False)
    with open(playlist_path , "w") as file:
        file.write("#EXTM3U")
        for i in range(len(content)):
            if content[i][0]!= '':
                base_path = "../../../3332-3734/Music/From spotify/"
                artist_id = select_row_in_table(conn, "lienartistmusic", "music_id", content[i][0], "artist_id", True)
                artist_name = select_row_in_table(conn, "artist", "id", artist_id[0][0], "name", True)
                album_id = select_row_in_table(conn, "music", "id", content[i][0], "album", True)
                album_name = select_row_in_table(conn, "album", "id", album_id[0][0], "name", True)
                music_name = select_row_in_table(conn, "music", "id", content[i][0], "title", True)
                music_path = base_path + artist_name[0][0] + album_name[0][0] +"/"+ music_name[0][0] + ".m4a"
                file.write("\n" + music_path)
                print(music_path)
                


#===========================================================
#===========================================================
#===========================================================
#                        EXECUTION
#===========================================================
#===========================================================
#===========================================================

#test

#Spotify test playlists
#=====================================

#playlist = "https://open.spotify.com/playlist/7gxLKaI7Ta1Rql8VQfDlYi"
#playlist = "https://open.spotify.com/playlist/37i9dQZF1DXbS5WTN5nKF7" 
#playlist = "https://open.spotify.com/album/0owIvIFEbUN6xtsplJHOjZ"

#====================================

conn = create_connection()
a, b = check_database(conn)
disconnect(conn)




ans = ""
print("\n Quelle est la playlist Spotify que vous voulez installer")
link = input("\n Lien google : ") 

print("1. Importer la playlist(crée une nouvelle playlist avec le même nom et les mêmes musiques). \n2. Installer chacune des musiques sans les ajouter à une playlist.\n3. Ajouter cette playlist à une autre.\n4. Vérifier l'intégrité de la base de donnée.")
ans = input("\n Que voulez vous faire : ") 
if ans == "1":
    conn = create_connection()
    final,youtubeLinks, extensions, name, ids = scrap(conn, link)
    table_names = tables(conn, "table")
    dl_only_musics(final, youtubeLinks, extensions)
    end = False
    while not end :
        if not name in table_names:
            print(f'{name} n était pas présente dans la base')
            create_playlist(conn, name)
            end = True
        else : 
            end = False
            print("\n1. Importer les musiques dans la playlist " + name + " \n2. Importer la plalist avec un autre nom.")
            ans = input("Que voulez-vous faire ?")
            if ans == "1":
                end = True
            if ans == "2":
                name = input("Quel nom souhaitez vous ?")
    add_to_playlist(name, ids, "Maxence Prout")
    disconnect(conn)
if ans == "2":
    conn = create_connection()
    final,youtubeLinks, extensions, name, ids = scrap(conn, link)
    dl_only_musics(final, youtubeLinks, extensions)
    disconnect(conn)
if ans == "3":
    conn = create_connection()
    final,youtubeLinks, extensions, name, ids = scrap(conn, link)
    dl_only_musics(final, youtubeLinks, extensions)
    name = input("Quel nom souhaitez vous pour la playlist ?")
    table_names = tables(conn, "table")
    while not end :
        if not name in table_names:
            print(f'{name} n était pas présente dans la base')
            create_playlist(conn, name)
            end = True
        else : 
            end = False
            print("\n1. Importer les musiques dans la playlist " + name + " \n2. Importer la plalist avec un autre nom.")
            ans = input("Que voulez-vous faire ?")
            if ans == "2":
                name = input("Quel nom souhaitez vous ?")
    add_to_playlist(name, ids, "Maxence Prout")
    disconnect(conn)

if ans == "4":
    conn = create_connection()
    ids, b = check_database(conn)
    print("1.Réinstaller les musiques \n2.Ne rien faire")
    ans = input("Que voulez-vous faire ?")
    if ans == "1":
        for i in range(len(ids)):
            musique = extract_all_info(conn, ids[i][0])
            dl_cover(musique[6], musique[0])
            yt_dl(musique)
            
    disconnect(conn)