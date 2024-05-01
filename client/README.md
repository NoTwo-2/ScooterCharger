# Setup

Please add setup instructions here!

# Setup the Pi for Temperature Sensor
1. In the Pi boot/config.txt file add the following line at the bottom:
dtoverlay=w1-gpio
2. Run the following commands:
   sudo modprobe w1-gpio
   sudo modprobe w1-thermo

# Setting up the Pi so it can take in input from the arduino:
1. Open Preferences and click Raspberry Pi Configuration
2. Go to interfaces
   Check Serial Port
   Make sure that Serial console is not checked
3. Reboot
# Setting up the Pi so it runs the script on startup
Add a line of code that will excecute client.py to /etc/rc.local

# Something about a boot script idk
