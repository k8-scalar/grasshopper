import sys

def update_config(value):
    with open('config.py', 'r') as file:
        lines = file.readlines()

    with open('config.py', 'w') as file:
        for line in lines:
            if line.startswith('singleSGPerNodeScenario'):
                line = f'singleSGPerNodeScenario={value.capitalize()}\n'
            file.write(line)

if len(sys.argv) != 2:
    print("Error: Please provide one argument for 'True' or 'False'.")
else:
    new_value = sys.argv[1].lower()
    if new_value not in ['true', 'false']:
        print("Invalid value. Please provide 'True' or 'False'.")
    update_config(new_value)



