This is the working prototype. It get's laggy after about 200-400 events. I will continue to make the events be trimmed but for now this is a full working proof of conecpt. 
This are the instructions to run.
Download all files and put into a folder, run CMD in the folder and point it at py poci_launcher.py
Make sure you have these installed in python (Not all are used i just have all them so im not sure which are required. 
requests
python-dotenv
aiohttp
openai
websockets
jsonrpcclient
rich
tqdm)

Open/download LM studio, open whatever model you would like to run and open it in a server. Make sure the Poci UI in the settings are pointed to the correct LM stuido Endpoint, along with the model listed correctly.
Start the POCI engine once it is pointed and the engine will start to send a heartbeat baseline prompt, and you can inject random prompts to watch the change in behavior. 
This is only my first working proof of concept prototype it is still heavily a work in progress. Not all features in the UI work like generating kaspa wallets etc, but the core concept is testable on all LM studio models at this point.
