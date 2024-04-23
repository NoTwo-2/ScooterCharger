import RPi.GPIO as GPIO

pin_to_power = 17
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_to_power,GPIO.OUT)

while True:
	user_action = input("What are we doing to pin:",pin_to_power,"?")
	if user_action == 'y':
		print("Sending Power")
		GPIO.output(pin_to_power,True)
	elif user_action == 'n':
		print("Turning Power Off")
		GPIO.output(pin_to_power,False
	elif user_action == 'x':
		print("Exiting")
		GPIO.output(pin_to_power,False)
		exit()
	else:
		print("Invalid Command")
