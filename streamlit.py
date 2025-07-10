import streamlit as st
import pandas as pd
import plotly.express as px
import calendar, re
from io import StringIO
from pathlib import Path

style_path = Path(__file__).parent / "style.css"

if style_path.exists():
    st.markdown(f"<style>{style_path.read_text()}</style>", unsafe_allow_html=True)
else:
    st.error("style.css not found.")

st.set_page_config(page_title="Listnd Dashboard", layout="wide")
st.title("Listnd Dashboard for the Year")

#popup with instructions
with st.expander("Instructions"):
    st.markdown("""
    ##### Welcome to Listnd, an app that tells you about your listening history across music listening platforms!     
    If you use multiple streaming platforms and have always wanted to know, comprehensively, who is your top artist? 
    Here is the place for you to find out!           
    In order to do this however (works best on a computer), you do have to separately request your data
    from each platform you use... which can take a couple hours... stay with me here.             
    Fortunately here are convenient instructions for how to do so:        

    ### Spotify
    Go to account settings > Security and Privacy > Account Privacy > Download Your Data > Select Account Data > Request Data       
    You may have to confirm this request in an email. Once you get the email confirming your data is ready to download, 
    press Download. You will get a zipped file, which you will have to unzip.         
    To find the file we need: Spotify Account Data / StreamingHistory_music_0.json        
    Upload this file to the site in the Spotify section.        

    ### Youtube Music      
    Go to Google Takeout for the account you want to get data for. From there deselect all checkboxes except 'Youtube and Youtube Music'.
     Click on Multiple Formats and scroll down to find 'history' and change the dropdown from HTML to JSON then click OK. Click 
     'All YouTube data included' and deselect all checkboxes except 'history' then click OK. Press Next Step and ensure you can 
     access where it is being downloaded to, it will only Export Once, and the file type is a .zip. Then Create Export.        
    Once you get the email confirming your data is ready to download, download it. You may have to unzip this file.       
    To find the file we need: Takeout / YouTube and YouTube Music / history / watch-history.json      
    Upload this file to the site in the YouTube Music section.    
    (Disclaimer: the way YouTube stores data is slighly strange so this may not be completely accurate )          

    ### Apple Music      
    Go to your Apple account > Privacy > Your Data > Manage your data > Get a copy of your data        
    Then select the checkbox for Apple Media Services Information, Continue, then Complete Request.  
    Wait until your data file is ready, then download this file. You may have to unzip this file.      
    To find the file we need: Apple_Media_Services.zip / Apple Music Activity / Apple Music Play Activity.csv     
    Upload this file to the site in the Apple Music section.     
    (I think this should work?)    
    """)

st.markdown("#### Upload Spotify File")
spotify_upload = st.file_uploader("StreamingHistory_music_0", type=["json"])

st.markdown("#### Upload YouTube Music File")
youtube_upload = st.file_uploader("watch-history", type=["json"])

st.markdown("#### Upload Apple Music File")
apple_upload = st.file_uploader("Apple Music Play Activity", type=["csv"])

year = st.multiselect("Select Year", [2023, 2024, 2025], default=[2024])

def parse_json(contents):
    stringio = StringIO(contents.getvalue().decode("utf-8"))
    return pd.read_json(stringio)

def parse_csv(contents):
    return pd.read_csv(contents)


def clean_spotify(spotify, year): 
    #Convert spotify endTime to datetime
    spotify['endTime'] = pd.to_datetime(spotify['endTime']) 
    spotify['date'] = spotify['endTime'].dt.date
    spotify['month'] = spotify['endTime'].dt.month
    spotify['hour'] = spotify['endTime'].dt.hour
    spotify['year'] = spotify['endTime'].dt.year
    spotify = spotify[spotify['year'].isin(year)] #only data from selected years
    spotify.rename(columns={'artistName': 'artist', 'trackName': 'title'}, inplace=True) #rename columns
    return spotify

def clean_youtube(youtube, year):
    #Clean Youtube
    youtube = youtube[youtube['header']=='YouTube Music'] #only take data from youtube music 
    youtube = youtube.drop(['titleUrl', 'products', 'activityControls', 'description', 'details', 'header'], axis=1)
    #Convert youtube ListTime to datetime
    youtube['ListTime'] = pd.to_datetime(youtube['time'], errors='coerce', utc=True)
    youtube['date'] = youtube['ListTime'].dt.date
    youtube['month'] = youtube['ListTime'].dt.month
    youtube['hour'] = youtube['ListTime'].dt.hour
    youtube['year'] = youtube['ListTime'].dt.year
    youtube = youtube[youtube['year'].isin(year)] #only take data from selected year

    #Clean Youtube Song Titles
    def delete_watched(value): #Eliminate 'Watched' from song titles
        pattern = r'^Watched '
        if re.match(pattern, value):
            cleaned = re.sub(r'^Watched ', '', value)
            return cleaned
    youtube['title'] = youtube['title'].apply(delete_watched) 

    #Get artist names from list in subtitles
    youtube = youtube[~youtube['subtitles'].apply(lambda x: isinstance(x, float))] #drop float rows
    def get_name(value): #Index artist names 
        return value[0]['name']
    youtube['artist'] = youtube['subtitles'].apply(get_name) #Make artist column 

    #Delete '- Topic' in Title 
    def delete_topic(value): 
        pattern = r'.*\- Topic$'
        if re.match(pattern, value):
            cleaned = re.sub(r' \- Topic', '', value)
            return cleaned, True #add cleaned_flag for songs with author
        else: return value, False
    youtube[['artist', 'cleaned_flag']] = youtube['artist'].apply(delete_topic).apply(pd.Series)

    #Eliminate random characters from titles and artists
    youtube['title'] = youtube['title'].str.replace(r"[•·]", " ", regex=True)
    youtube['artist'] = youtube['artist'].str.replace(r"[•·]", " ", regex=True)

    artists = youtube[youtube['cleaned_flag']==True]['artist'].unique() #Create list of clean artists
    sorted_artists = sorted(artists, key=len, reverse=True) #sort greatest to shortest to match longest
    
    #Find artist from artist name in title
    def find_artist(title): #Function to find artist name in title
        for artist in artists:
            if artist.lower() in title.lower():
                return artist
        return None
    for idx, row in youtube[~youtube['cleaned_flag']].iterrows():
        artist_found = find_artist(row['title']) #change artist if found in title
        if artist_found:
            youtube.at[idx, 'artist'] = artist_found 

    #Clean random words from song title
    def clean_title(title):
        for artist in artists: #eliminate artist from title
            pattern = re.compile(re.escape(artist), re.IGNORECASE)
            title = pattern.sub('', title)
        cuts = ['(Un-Official Video)', '(Official Video)', '(lyrics)', '-', '(Official)', '(Audio)', '(Official Music Video)', '(feat. )']
        for phrase in cuts: #eliminate phrases from title
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            title = pattern.sub('', title)
        title = title.strip()
        return title
    youtube['title'] = youtube['title'].apply(clean_title)

    return youtube

def clean_apple(apple, year):
    apple = apple[apple['Content Specific Type']=='Song'] #only take data of songs
    #Convert apple endTime to datetime
    apple['Event End Timestamp'] = pd.to_datetime(apple['Event End Timestamp']) 
    apple['date'] = apple['Event End Timestamp'].dt.date
    apple['month'] = apple['Event End Timestamp'].dt.month
    apple['hour'] = apple['Event End Timestamp'].dt.hour
    apple['year'] = apple['Event End Timestamp'].dt.year
    apple = apple[apple['year'].isin(year)] #only data from selected year
    apple.rename(columns={'Artist Name': 'artist', 'Content Name': 'title'}, inplace=True) #rename columns

    return apple

def dataframe_merge(spotifydf, youtubedf, appledf, selected_platform):
    df = []

    if 'spotify' in selected_platform:
        spotify2 = spotifydf[['artist', 'title', 'date', 'hour', 'month']] #Take only select columns
        spotify2['platform'] = 'spotify'
        df.append(spotify2)

    if 'youtube' in selected_platform:
        youtube2 = youtubedf[['artist', 'title', 'date', 'hour', 'month']]
        youtube2['platform'] = 'youtube'
        df.append(youtube2)

    if 'apple' in selected_platform:
        apple2 = appledf[['artist', 'title', 'date', 'hour', 'month']]
        apple2['platform'] = 'apple'
        df.append(apple2)

    if df:
        music = pd.concat(df, ignore_index=True)
        return music

def make_topsongs(dataframe):
    song_counts = dataframe.groupby(['title', 'artist']).size().reset_index(name='count')
    top10 = song_counts.sort_values('count', ascending=False).head(10)

    fig = px.bar(top10, x="title", y="count", color="artist", 
                 color_discrete_sequence=px.colors.qualitative.Pastel, 
             orientation="v", title="Top 10 Songs")
    fig.update_layout(
        xaxis=dict(categoryorder='array', categoryarray=top10['title'].tolist()), height=600)
    
    st.plotly_chart(fig, use_container_width=True)

def make_topartists(dataframe):
    #For pie chart
    artist_freq = dataframe['artist'].value_counts().reset_index()
    artist_freq.columns = ['artist', 'count'] #frequency of top artists 
    artist_freq = artist_freq.reset_index()
    top_artist = artist_freq.sort_values('count', ascending=False)
    artist10 = top_artist.head(10)

    #For line graph of top 5 artists over time
    top5_art = top_artist['artist'].head(5).unique() #list of top 5 artists
    top5 = dataframe[dataframe['artist'].isin(top5_art)]
    monthly_counts = top5.groupby(['artist', 'month']).size().reset_index(name='listen_count')

    pie = px.pie(artist10, values='count', names='artist', title="Top 10 Artists")
    st.plotly_chart(pie)
    
    bar = px.histogram(top5, x='hour', color='artist', nbins=24, barmode='stack', title='Top 5 Artists Through the Day')
    bar.update_layout(xaxis_title='Hour of Day', yaxis_title='Listen Count')
    st.plotly_chart(bar)

def make_choiceline(dataframe, line_choice):
    if line_choice == "Songs":
        song_counts = dataframe.groupby(['title', 'artist']).size().reset_index(name='count')
        top10 = song_counts.sort_values('count', ascending=False).head(10)
        top5_song = top10['title'].head(5).unique() #list of top 5 songs
        top5_song = music[music['title'].isin(top5_song)]
        monthly_song = top5_song.groupby(['title', 'month']).size().reset_index(name='listen_count')

        line = px.line(monthly_song, x="month", y="listen_count", color="title", title="Top 5 Songs Through the Year")
        line.update_layout(xaxis_title='Month of Year', yaxis_title='Listen Count')
        st.plotly_chart(line)

    elif line_choice == "Artists":
        #For line graph of top 5 artists over time
        artist_counts = dataframe.groupby(['artist', 'artist']).size().reset_index(name='count')
        top10 = artist_counts.sort_values('count', ascending=False).head(10)
        top5 = top10['artist'].head(5).unique()
        top5 = dataframe[dataframe['artist'].isin(top5_art)]
        monthly_counts = top5.groupby(['artist', 'month']).size().reset_index(name='listen_count')

        line = px.line(monthly_counts, x="month", y="listen_count", color="artist", title="Top 5 Artists Through the Year")
        line.update_layout(xaxis_title='Month of Year', yaxis_title='Listen Count')
        st.plotly_chart(line)

def make_platform(dataframe, platforms):
    if len(platforms) == 1:
        st.success(f"Analysed all of your data from {', '.join(platforms)} :)")
    fig = px.histogram(dataframe, x='date', color='platform', nbins=24, barmode='stack',
    title='Platforms Used Throughout The Year')
    fig.update_layout(xaxis_title='date', yaxis_title='songs')
    st.plotly_chart(fig)

def monthly_analysis(dataframe, months):
    mdf = dataframe[dataframe['month'].isin(months)]
    monthly_artists = mdf.groupby(['artist']).size().reset_index(name='count')
    top5 = monthly_artists.sort_values('count', ascending=False).head(5)
    pie = px.pie(top5, values='count', names='artist', title="Top 5 Artists for Select Months")
    st.plotly_chart(pie)

if spotify_upload or youtube_upload or apple_upload:
    spotify, youtube, apple = None, None, None

    platform_options = []
    if spotify_upload:
        spotify = parse_json(spotify_upload)
        spotify = clean_spotify(spotify, year=year)
        platform_options.append('spotify') 

    if youtube_upload:
        youtube = parse_json(youtube_upload)
        youtube = clean_youtube(youtube, year=year)
        platform_options.append('youtube')

    if apple_upload:
        apple = parse_csv(apple_upload)
        apple = clean_apple(apple, year=year)
        platform_options.append('apple')

    platforms = st.multiselect("Select Platforms:", options=platform_options, default=platform_options)

    if platforms:
        music = dataframe_merge(spotify, youtube, apple, platforms)
    
        if music.empty:
            st.warning("No data found after filtering.")
        if not music.empty:
            st.header("Top Songs")
            make_topsongs(music)
            st.header("Top Artists")
            make_topartists(music)

            st.header("Top 5 in the Year")
            chosen_line = st.radio("Select what to see top 5 of:", options=["Artists", "Songs"], index=0)
            make_choiceline(music, chosen_line)

            st.header("Monthly Analysis")
            month_options={i:month for i, month in enumerate(calendar.month_name) if month}
            selected_months = st.multiselect("Select Months for Further Analysis", options=list(month_options.keys()),
                format_func=lambda x: month_options[x], default=[1])
            if selected_months:
                monthly_analysis(music, selected_months)
else:
    st.info("Upload at least one file")