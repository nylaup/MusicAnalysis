# MusicAnalysis
A website that creates a spotify wrapped like music analysis for downloaded listening data from a variety of platforms. 

## How to Download Listening Data?

### Spotify
Go to account settings > Security and Privacy > Account Privacy > Download Your Data > Select Account Data > Request Data 
You may have to confirm this request in an email. Once you get the email confirming your data is ready to download, press Download. You will get a zipped file, which you will have to unzip. 
To find the file we need: Spotify Account Data / StreamingHistory_music_0.json
Upload this file to the site in the Spotify section.

### Youtube Music
Go to Google Takeout for the account you want to get data for. From there deselect all checkboxes except 'Youtube and Youtube Music'. Click on Multiple Formats and scroll down to find 'history' and change the dropdown from HTML to JSON then click OK. Click 'All YouTube data included' and deselect all checkboxes except 'history' then click OK. Press Next Step and ensure you can access where it is being downloaded to, it will only Export Once, and the file type is a .zip. Then Create Export. 
Once you get the email confirming your data is ready to download, download it. You may have to unzip this file. 
To find the file we need: Takeout / YouTube and YouTube Music / history / watch-history.json
Upload this file to the site in the YouTube Music section. 

### Apple Music
Go to your Apple ID account, request a copy of your data and select only apple music data. Wait until your data file is ready, then download this file. You may have to unzip thsi file.
To find the file we need: Apple_Media_Services.zip / Apple Music Activity / Apple Music Play Activity.csv