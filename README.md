# zx-next-pi0-tzxplayer
 A TZX Player that runs on the pi0 inside a ZX Next.

This is a fully functional TZX player for the pi0 that is
hidden inside the accelerated version of the ZX Spectrum
Next. However, this will not work our of the box you will
require my custom version of DietPi running on your Raspi.

I have yet to name or release my version but rest assured
it will be available at some point in the future.

This is a python3 backend server with a little HTML/JS to 
present the user interface. A Loader is loaded into the ZX
Next who then waits for audio data to arrive over the
internal I2S connection. 

Browse to the IP of the pi0 on port 5000 will show the GUI.
This is something like http://192.168.0.236:5000 

TZX files are converted to WAV format on upload and take 
a few moments for this to complete. You should be able to 
successfuly use the the Play/Pause button for multi load 
games - I have not yet added seek but the progress bar is 
there - maybe you have a pull request you want to submit?

If you are using my custom DietPi then everything you need
should come pre-installed:
python3 
sox  

The python server should be started by the loader - or
manually python3 server.py 

The server expects to run out of var/www/docs/ - why 
docs? No particular reason other than that is where it
started out - feel free to update.

Enjoy!

