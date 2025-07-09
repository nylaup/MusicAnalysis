import pandas as pd
import streamlit as st
import plotly.express as px
import re, dash, base64, calendar, webbrowser
from io import BytesIO, StringIO

st.set_page_config(page_title="Listnd Dashboad", layout="wide")
st.title("Listnd Dashboard for the Year")

spotify_upload = st.file_uploader("Upload Spotify File", type["json"])
youtube_upload = st.file_uploader("Upload Youtube File", type["json"])

year = st.selectbox("Select Year", [2023, 2024, 2025], index=1)

def parse_contents(contents):
    stringio = StringIO(upload.getvalue().decode("utf-8"))
    return pd.read_json(stringio)

def clean_spotify(spotify, year): 
    #Convert spotify endTime to datetime
    spotify['endTime'] = pd.to_datetime(spotify['endTime']) 
    spotify['date'] = spotify['endTime'].dt.date
    spotify['month'] = spotify['endTime'].dt.month
    spotify['hour'] = spotify['endTime'].dt.hour
    spotify['year'] = spotify['endTime'].dt.year
    spotify = spotify[spotify['year']==year] #only data from 2024
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
    youtube = youtube[youtube['year']==year] #only take data from 2024

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

def dataframe_merge(spotifydf, youtubedf, selected_platform):
    df = []

    if 'spotify' in selected_platform:
        spotify2 = spotifydf[['artist', 'title', 'date', 'hour', 'month']] #Take only select columns
        spotify2['platform'] = 'spotify'
        df.append(spotify2)

    if 'youtube' in selected_platform:
        youtube2 = youtubedf[['artist', 'title', 'date', 'hour', 'month']]
        youtube2['platform'] = 'youtube'
        df.append(youtube2)

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

    line = px.line(monthly_counts, x="month", y="listen_count", color="artist", title="Top 5 Artists Through the Year")
    line.update_layout(xaxis_title='Month of Year', yaxis_title='Listen Count')
    st.plotly_chart(line)

    bar = px.histogram(top5, x='hour', color='artist', nbins=24, barmode='stack', title='Top 5 Artists Through the Day')
    bar.update_layout(xaxis_title='Hour of Day', yaxis_title='Listen Count')
    st.plotly_chart(bar)

def make_platform(dataframe, platforms):
    if len(platforms) == 1:
        return html.Div(f"Analysed all of your data from {platforms[0]} :)")
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

if spotify_upload or youtube_upload:
    spotify, youtube = None, None

    if spotify_upload:
        spotify = parse_contents(spotify_upload)
        spotify = clean_spotify(spotify, year=year) 

    if youtube_upload:
        youtube = parse_contents(youtube_upload)
        youtube = clean_youtube(youtube, year=year)

    platform_options = []
    if spotify_content:
        platform_options.append('spotify')
    if youtube_content:
        platform_options.append('youtube')
    platforms = st.multiselect("Select Platforms:", options=platform_options, default=platform_options)

    if platforms:
        music = dataframe_merge(spotify, youtube, platforms)
    
        if music.empty:
            return html.Div("No data available"), None, None, None
        if not music.empty:
            st.header("Top Songs")
            make_topsongs(music)
            st.header("Top Artists")
            make_topartists(music)

            st.header("Monthly Analysis")
            month_options={i:month for i, month in enumerate(calendar.month_name) if month}
            selected_months = st.multiselect("Select Months", options=list(month_options.keys()),
                format_func=lambda x: month_options[x], default=[1])
            if selected_months:
                monthly_analysis(music, selected_months)
else:
    st.info("Upload at least one file")