import streamlit as st
import pandas as pd
import plotly.express as px
import calendar, re
from io import StringIO

with open("style.css") as f:
    css = f.read()
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Listnd Dashboard", layout="wide")
st.title("Listnd Dashboard for the Year")

#popup with instructions
with st.expander("Instructions"):
    st.markdown("""
    ##### Welcome to Listnd, an app that tells you about your listening history across music listening platforms!     
    If you use multiple streaming platforms and have always wanted to know, comprehensively, who is your top artist? 
    Here is the place for you to find out!       
    If not, you can also see some fun graphs from just one app.     
    In order to do this however (works best on a computer), you do have to separately request your data
    from each platform you use... which can take a couple days... stay with me here.             
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
    (Disclaimer: the way YouTube stores data is slighly strange so this may not be completely accurate. It also doesn't give minutes listened)          

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
    spotify['hour'] = spotify['endTime'].dt.strftime('%I %p')  
    spotify['hour'] = spotify['hour'].str.lstrip('0')
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
    youtube['hour'] = youtube['ListTime'].dt.strftime('%I %p') 
    youtube['hour'] = youtube['hour'].str.lstrip('0')
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
    apple['hour'] = apple['Event End Timestamp'].dt.strftime('%I %p') 
    apple['hour'] = apple['hour'].str.lstrip('0')
    apple['year'] = apple['Event End Timestamp'].dt.year
    apple = apple[apple['year'].isin(year)] #only data from selected year
    apple.rename(columns={'Artist Name': 'artist', 'Content Name': 'title', 'End Position In Milliseconds':'msPlayed'}, inplace=True) #rename columns

    return apple

def dataframe_merge(spotifydf, youtubedf, appledf, selected_platform):
    df = []

    if 'spotify' in selected_platform:
        spotify2 = spotifydf[['artist', 'title', 'date', 'hour', 'month', 'msPlayed']] #Take only select columns
        spotify2['platform'] = 'spotify'
        df.append(spotify2)

    if 'youtube' in selected_platform:
        youtube2 = youtubedf[['artist', 'title', 'date', 'hour', 'month']]
        youtube2['msPlayed'] = None
        youtube2['platform'] = 'youtube'
        df.append(youtube2)

    if 'apple' in selected_platform:
        apple2 = appledf[['artist', 'title', 'date', 'hour', 'month', 'msPlayed']]
        apple2['platform'] = 'apple'
        df.append(apple2)

    if df:
        music = pd.concat(df, ignore_index=True)
        return music

def make_facts(dataframe, platforms):
    #Biggest listening day and artist for that day 
    dataframe['date'] = pd.to_datetime(dataframe['date'])
    daily_counts = dataframe.groupby(['date']).size().reset_index(name='listen_count').sort_values('listen_count', ascending=False)
    top_day = daily_counts.iloc[0]['date']
    topday_count = daily_counts.iloc[0]['listen_count']
    topday_df = dataframe[dataframe['date']==top_day]
    topday_df = topday_df.groupby(['artist']).size().reset_index(name='listen_count').sort_values('listen_count', ascending=False)
    topday_artist = topday_df.iloc[0]['artist']
    top_day = pd.to_datetime(top_day).strftime('%m-%d')
    topday_text = f"You listened to {topday_count} songs on {top_day}! Big day for you. Big day for being a fan of {topday_artist} too it seems."

    #Most repeated song on one day
    repeat_counts = dataframe.groupby(['date','title']).size().reset_index(name='listen_count').sort_values('listen_count', ascending=False)
    repeated_song = repeat_counts.iloc[0]['title']
    repeated_day = pd.to_datetime(repeat_counts.iloc[0]['date']).strftime('%m-%d')
    repeated_counts = repeat_counts.iloc[0]['listen_count']
    repeat_text = f"You listened to {repeated_song} {repeated_counts} times on {repeated_day}. A new record for you. It's that good?"

    #Number of unique songs listened to
    num_songs=repeat_counts.size
    if num_songs > 15921:
        num_text = f"Wow! You listened to {num_songs} songs. Better than me..."
    elif num_songs < 15921:
        num_text = f"Huh, you only listened to {num_songs} songs... I could do better."
    else:
        num_text = f"You listened to {num_songs} songs. Samesies!"

    #Compare listening by minutes
    if all(p == "youtube" for p in platforms): #cant do this with just youtube
        minutes_text = ":)" 
    else:
        disc=""
        if ("youtube" in platforms): #disclaimer if user uses youtube
            disc = "(Youtube Music does not give time listened, so this is your music minus Youtube!) \n"
        music2 = dataframe.dropna() #drop values with no time
        mostminutes = music2.groupby('artist')['msPlayed'].sum().reset_index().sort_values('msPlayed', ascending=False)
        mostminutes['hours'] = mostminutes['msPlayed'] / 3600000 #get hours
        topmins = mostminutes.head(5)['artist'].tolist() #get top 5 most minutes
        topsongs = music2.groupby(['artist']).size().reset_index(name='listen_count').sort_values('listen_count', ascending=False).head(5)
        topsongs = topsongs['artist'].tolist()
        if (sorted(topsongs) == sorted(topmins)):
            text1 = "the same artists"
            if (topsongs==topmins):
                text2 = "and in the same order!"
            else:
                text2 = " but not in the same order."
        else:
            text1= "different artists"
            text2= ", interesting"

        minutes_text =(f"{disc} Dang! {round(mostminutes.iloc[0]['hours'], 1)} hours of {mostminutes.iloc[0]['artist']}. Moving on... \n" 
                f"If we look at listening based on minutes, your top artists are {', '.join(topmins)}.\n" 
                f"Which is interesting when compared to top artists by song. You've got {text1} {text2}")

    st.text(num_text)
    st.text(topday_text)
    st.text(repeat_text)
    st.text(minutes_text)

def make_topsongs(dataframe):
    #Barchart of top artists
    song_counts = dataframe.groupby(['title', 'artist']).size().reset_index(name='count')
    top10 = song_counts.sort_values('count', ascending=False).head(10)

    fig = px.bar(top10, x="title", y="count", color="artist", 
                 color_discrete_sequence=px.colors.qualitative.Pastel, 
             orientation="v", title="Top 10 Songs")
    fig.update_layout(
        xaxis=dict(categoryorder='array', categoryarray=top10['title'].tolist()), height=600)
    st.plotly_chart(fig, use_container_width=True)

    #Linegraph of top artists
    song_counts = dataframe.groupby(['title', 'artist']).size().reset_index(name='count')
    top10 = song_counts.sort_values('count', ascending=False).head(10)
    top5_song = top10['title'].head(5).unique() #list of top 5 songs
    top5_songs = dataframe[dataframe['title'].isin(top5_song)]
    monthly_song = top5_songs.groupby(['title', 'month']).size().reset_index(name='listen_count')

    line = px.line(monthly_song, x="month", y="listen_count", color="title", title="Top 5 Songs Through the Year")
    line.update_layout(xaxis_title='Month of Year', yaxis_title='Listen Count')
    st.plotly_chart(line)

def make_topartists(dataframe):
    #For pie chart
    artist_freq = dataframe['artist'].value_counts().reset_index()
    artist_freq.columns = ['artist', 'count'] #frequency of top artists 
    artist_freq = artist_freq.reset_index()
    top_artist = artist_freq.sort_values('count', ascending=False)
    artist10 = top_artist.head(10)

    pie = px.pie(artist10, values='count', names='artist', title="Top 10 Artists")
    st.plotly_chart(pie)
    

    #Barchart of top 3
    monthly_counts = dataframe.groupby(['artist', 'month']).size().reset_index(name='listen_count')
    top5_artists_overall = (monthly_counts.groupby('artist')['listen_count'].sum().sort_values(ascending=False)
        .head(5).index.tolist())
    color_palette = px.colors.qualitative.Plotly
    custom_color_map = {artist: color_palette[i] for i, artist in enumerate(top5_artists_overall)}
    top3_artists = pd.DataFrame()
    for month in range(1,13):
        df = monthly_counts[monthly_counts['month']==month]
        df = df.sort_values('listen_count', ascending=False).head(3)
        top3_artists = pd.concat([top3_artists, df])
    top3_artists = top3_artists.sort_values(by=["month", "listen_count"], ascending=[True, False])
    def generate_grayscale(n, start=200, end=80):
        step = (start - end) // max(n - 1, 1)
        return [f"#{v:02x}{v:02x}{v:02x}" for v in range(start, end - 1, -step)]
    grayscale_colors = generate_grayscale(10) 
    all_artists = top3_artists['artist'].unique()
    non_top5_artists = [a for a in all_artists if a not in top5_artists_overall]
    for i, artist in enumerate(non_top5_artists):
        custom_color_map[artist] = grayscale_colors[i % len(grayscale_colors)]

    fig = px.bar(top3_artists, x="month", y="listen_count", color="artist", 
             color_discrete_map=custom_color_map, barmode="stack", title="Top 3 artists per month")
    for trace in fig.data: #Legend only has top5
        if trace.name not in top5_artists_overall:
            trace.showlegend = False
    st.plotly_chart(fig)

def make_platform(dataframe, platforms):
    if len(platforms) == 1:
        st.success(f"Analysed all of your data from {', '.join(platforms)} :)")
    else: 
        fig = px.histogram(dataframe, x='date', color='platform', nbins=24, barmode='stack',
        title='Platforms Used Throughout The Year')
        fig.update_layout(xaxis_title='date', yaxis_title='songs')
        st.plotly_chart(fig)

def monthly_analysis(dataframe, months, subject):
    mdf = dataframe[dataframe['month'].isin(months)]
    if subject == "Artists":
        monthly_artists = mdf.groupby(['artist']).size().reset_index(name='count')
        top5 = monthly_artists.sort_values('count', ascending=False).head(5)
        pie = px.pie(top5, values='count', names='artist', title="Top 5 Artists for Select Months")
        st.plotly_chart(pie)
    elif subject == "Songs":
        monthly_songs = mdf.groupby(['title']).size().reset_index(name='count')
        top5 = monthly_songs.sort_values('count', ascending=False).head(5)
        pie = px.pie(top5, values='count', names='title', title="Top 5 Songs for Select Months")
        st.plotly_chart(pie)
    
def artist_info(dataframe, chosen_artist):
    bigdog = dataframe[dataframe['artist']==chosen_artist]
    bigdog_music = bigdog.groupby(['title']).size().reset_index(name='count').sort_values('count', ascending=False).head(3)
    favsongs = bigdog_music['title'].tolist()

    first_listen = bigdog['date'].min().strftime('%m-%d')
    say= f"Love at first sight... On {first_listen}, precisely, for you and {chosen_artist} that is. \nSince then you've been a big fan of {", ".join((favsongs)[:2])}, and {favsongs[2]}."
    st.text(say)

def make_hours(dataframe):
    dataframe['day_name'] = dataframe['date'].dt.day_name()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    hour_order = ['12 AM', '1 AM', '2 AM', '3 AM', '4 AM', '5 AM','6 AM', '7 AM', '8 AM', '9 AM', '10 AM', '11 AM',
        '12 PM', '1 PM', '2 PM', '3 PM', '4 PM', '5 PM','6 PM', '7 PM', '8 PM', '9 PM', '10 PM', '11 PM']
    fig = px.density_heatmap(dataframe, x='hour', y='day_name', category_orders={'day_name':day_order, 'hour':hour_order}, title="Music Listening Through the Week")
    fig.update_layout(yaxis_title="Day of the Week", xaxis_title="Hour")
    st.plotly_chart(fig)

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

            st.header("Listening Facts")
            make_facts(music, platforms)

            st.header("Hourly Analysis")
            make_hours(music)

            st.header("Monthly Analysis")
            chosen_analysis = st.radio("Select what you want a deeper dive on:", options=["Artists", "Songs"], index=0)
            month_options={i:month for i, month in enumerate(calendar.month_name) if month}
            selected_months = st.multiselect("Select Months for Further Analysis", options=list(month_options.keys()),
                format_func=lambda x: month_options[x], default=[1])
            if selected_months:
                monthly_analysis(music, selected_months, chosen_analysis)

            st.header("Artist Info")
            big10arts = music.groupby('artist').size().reset_index(name='listen_count').sort_values('listen_count', ascending=False).head(10)['artist']
            select_artist = st.selectbox("Select Artist for Further Analysis", options=list(big10arts))
            artist_info(music, select_artist)

            st.header("Platform Analysis")
            make_platform(music, platforms)
else:
    st.info("Upload at least one file")
