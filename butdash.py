import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import re, dash, base64, calendar, webbrowser
from dash import dcc, html, Dash, Input, Output
from io import BytesIO


#Read in Data 
spotify = pd.read_json('Spotify Account Data\StreamingHistory_music_0.json')
youtube = pd.read_json('Takeout\YouTube and YouTube Music\history\watch-history.json')

def clean_spotify(spotify, year): 
    #Convert spotify endTime to datetime
    spotify['endTime'] = pd.to_datetime(spotify['endTime']) 
    spotify['date'] = pd.to_datetime(spotify['endTime'].dt.date)
    spotify['time'] = spotify['endTime'].dt.strftime('%H:%M')
    spotify['hour'] = spotify['endTime'].dt.strftime('%H') #need hour for graph
    spotify['hour'] = pd.to_numeric(spotify['hour']) 
    spotify['year'] = spotify['endTime'].dt.strftime('%Y')
    spotify['year'] = pd.to_numeric(spotify['year'])
    spotify['month'] = spotify['endTime'].dt.strftime('%m')
    spotify['month'] = pd.to_numeric(spotify['month'])
    spotify = spotify[spotify['year']==year] #only data from 2024
    spotify.rename(columns={'artistName': 'artist', 'trackName': 'title'}, inplace=True) #rename columns
    return spotify

def clean_youtube(youtube, year):
    #Clean Youtube
    youtube = youtube[youtube['header']=='YouTube Music'] #only take data from youtube music 
    youtube = youtube.drop(['titleUrl', 'products', 'activityControls', 'description', 'details', 'header'], axis=1)
    #Convert youtube ListTime to datetime
    youtube['ListTime'] = pd.to_datetime(youtube['time'], errors='coerce', utc=True)
    youtube['date'] = pd.to_datetime(youtube['ListTime'].dt.date) 
    youtube['time'] = youtube['ListTime'].dt.strftime('%H:%M')
    youtube['hour'] = youtube['ListTime'].dt.strftime('%H')
    youtube['hour'] = pd.to_numeric(youtube['hour'])
    youtube['year'] = youtube['ListTime'].dt.strftime('%Y')
    youtube['year'] = pd.to_numeric(youtube['year'])
    youtube['month'] = youtube['ListTime'].dt.strftime('%m')
    youtube['month'] = pd.to_numeric(youtube['month'])
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
    def delete_topic(value): #delete '- Topic' in names 
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

spotify = clean_spotify(spotify, year=2024)
youtube = clean_youtube(youtube, year=2024)

def make_topsongs(dataframe):
    song_counts = dataframe.groupby(['title', 'artist']).size().reset_index(name='count')
    top10 = song_counts.sort_values('count', ascending=False).head(10)

    fig = px.bar(top10, x="title", y="count", color="artist", 
                 color_discrete_sequence=px.colors.qualitative.Pastel, 
             orientation="v", title="Top 10 Songs")
    fig.update_layout(
        xaxis=dict(categoryorder='array', categoryarray=top10['title'].tolist()))
    fig.update_layout(height=600)
    return dcc.Graph(figure=fig)

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
    line = px.line(monthly_counts, x="month", y="listen_count", color="artist", title="Top 5 Artists Through the Year")
    line.update_layout(xaxis_title='Month of Year', yaxis_title='Listen Count')
    bar = px.histogram(top5, x='hour', color='artist', nbins=24, barmode='stack', title='Top 5 Artists Through the Day')
    bar.update_layout(xaxis_title='Hour of Day', yaxis_title='Listen Count')
    return html.Div([dcc.Graph(figure=pie), dcc.Graph(figure=line), dcc.Graph(figure=bar)])

def make_platform(dataframe, platforms):
    if len(platforms) == 1:
        return html.Div(f"Analysed all of your data from {platforms[0]} :)")
    fig = px.histogram(dataframe, x='date', color='platform', nbins=24, barmode='stack',
    title='Platforms Used Throughout The Year')
    fig.update_layout(xaxis_title='date', yaxis_title='songs')
    return dcc.Graph(figure=fig)

def monthly_analysis(dataframe, months):
    mdf = dataframe[dataframe['month'].isin(months)]
    monthly_artists = mdf.groupby(['artist']).size().reset_index(name='count')
    top5 = monthly_artists.sort_values('count', ascending=False).head(5)
    pie = px.pie(top5, values='count', names='artist', title="Top 5 Artists for Select Months")
    return dcc.Graph(figure=pie)


app=Dash() #Create app
app.title="Listnd"

app.layout = html.Div([
    html.H1("Listnd Dashboard for the Year"),
    html.Div([
        html.Div([
            html.Label("Select Platforms:"),
            dcc.Dropdown(
                id='platform-selected',
                options=[{'label': p, 'value': p.lower()} for p in ['Spotify', 'YouTube']],
                value=['spotify', 'youtube'],multi=True
            )
        ], style={'width': '48%', 'padding': '10px'}),

        html.Div([
            html.Label("Select Year:"),
            dcc.Dropdown(
                id='year-selected',
                options=[{'label': str(y), 'value': y} for y in [2023, 2024, 2025]],
                value=2024, clearable=False
            )
        ], style={'width': '48%', 'padding': '10px'}),
    ], style={'display': 'flex', 'flex-wrap': 'wrap', 'margin-bottom': '20px'}),
    html.H2("Top Songs"),
    html.Div(id='topsongs-graph'),
    html.H2("Top Artists"),
    html.Div(id='topartists-graphs'),
    html.H2("Monthly Analysis"),
    html.Div([
        html.Div([
            html.Label("Select Months:"),
            dcc.Checklist(
                id='monthly',
                options=[{'label': month, 'value': i} for i, month in enumerate(calendar.month_name) if month],
                value=[1]
            ),
        ], style={'width': '100%', 'padding': '10px', 'marginRight': 'auto'},
        ),
        html.Div([
            html.Div(id='monthly-graphs')
        ], style={'width': '70%', 'padding': '10px', 'marginLeft': 'auto'}
        )
    ], style={'display': 'flex', 'alignItems': 'center'}
    ),
    html.H2("Platforms"),
    html.Div(id='platform-graph')
], style={'max-width': '1200px', 'margin': '0 auto', 'font-family': 'Calibri, sans-serif'}
)



@app.callback(
    Output('topsongs-graph', 'children'),
    Output('topartists-graphs', 'children'),
    Output('monthly-graphs', 'children'),
    Output('platform-graph', 'children'),
    Input('platform-selected', 'value'),
    Input('year-selected', 'value'),
    Input('monthly', 'value')
)

def update_graphs(selected_platforms, selected_year, selected_months):
    # Filter music by platform and year
    music = dataframe_merge(spotify, youtube, selected_platforms)
    music = music[music['date'].dt.year == int(selected_year)]
    
    # Build figures (you can modularize to helper functions passing filtered_music)
    top_songs_fig = make_topsongs(music)
    top_artists_figs = make_topartists(music)
    monthly_fig = monthly_analysis(music, selected_months)
    platform_fig = make_platform(music, selected_platforms)

    return top_songs_fig, top_artists_figs, monthly_fig, platform_fig


if __name__=="__main__":
    webbrowser.open("http://127.0.0.1:8050/")
    app.run(debug=True)

