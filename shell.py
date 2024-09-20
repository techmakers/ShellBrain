import openai
import subprocess
import json
import time
import sys
import os
import argparse
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

# ANSI color codes
COLORS = {
    'RED': '\033[91m',
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'BLUE': '\033[94m',
    'MAGENTA': '\033[95m',
    'CYAN': '\033[96m',
    'LIGHT_CYAN': '\033[96;1m',  # Light Cyan and Bold
    'WHITE': '\033[97m',
    'RESET': '\033[0m'
}

# Function to print colored text
def print_colored(text, color='WHITE'):
    color_code = COLORS.get(color.upper(), COLORS['WHITE'])
    print(f"{color_code}{text}{COLORS['RESET']}")

# Function to execute a shell command and return its output
def execute_shell_command(command):
    try:
        # Print the command that will be executed
        print_colored(f"\nExecuting command: {command}", 'GREEN')
        print_colored("Starting execution...", 'GREEN')

        # Check if the command is a cd command
        if command.strip().startswith('cd'):
            # Extract the directory path
            new_dir = command.strip()[3:].strip()
            try:
                os.chdir(new_dir)
                print_colored(f"Changed directory to: {os.getcwd()}", 'GREEN')
                return f"Changed directory to: {os.getcwd()}"
            except FileNotFoundError:
                print_colored(f"Directory not found: {new_dir}", 'RED')
                return f"Error: Directory not found: {new_dir}"
            except PermissionError:
                print_colored(f"Permission denied: {new_dir}", 'RED')
                return f"Error: Permission denied: {new_dir}"

        # Check if the command is an interactive program
        interactive_programs = ['nano', 'vim', 'emacs', 'less', 'more']
        command_parts = command.split()
        if command_parts and command_parts[0] in interactive_programs:
            print_colored("Interactive program detected. Launching...", 'YELLOW')
            os.system(command)
            print_colored("Interactive program closed. Returning to script.", 'YELLOW')
            return "Interactive program execution completed."

        # For non-interactive commands, use subprocess
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Print dots while the command is running
        while process.poll() is None:
            sys.stdout.write(f"{COLORS['GREEN']}.{COLORS['RESET']}")
            sys.stdout.flush()
            time.sleep(0.5)

        # Get the output
        stdout, stderr = process.communicate()

        print_colored("\nExecution completed.", 'GREEN')

        if process.returncode == 0:
            return stdout
        else:
            return f"Error: {stderr}"
    except Exception as e:
        return f"Error in execution: {str(e)}"

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Interactive shell with OpenAI integration")
    parser.add_argument("--keep", action="store_true", help="Keep conversation context")
    parser.add_argument("-y", action="store_true", help="Execute commands without confirmation")
    parser.add_argument("--api-key", help="OpenAI API key")
    args = parser.parse_args()

    # Get the OpenAI API key
    api_key = args.api_key or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print_colored("Error: OpenAI API key not provided. Please use --api-key or set the OPENAI_API_KEY environment variable.", 'RED')
        sys.exit(1)

    # Initialize OpenAI API with the API key
    openai.api_key = api_key

    # Create a PromptSession with FileHistory
    session = PromptSession(history=FileHistory('.command_history'))

    # Initialize conversation history
    conversation_history = []
    if args.keep:
        conversation_history.append({"role": "system", "content": "You are a helpful assistant that can execute shell commands and provide information."})

    while True:
        try:
            # Use prompt_toolkit to get user input with history
            user_input = session.prompt(f"\n{os.getcwd()}> ")

            if user_input.lower() == 'exit':
                break

            # Add user input to conversation history if --keep is enabled
            if args.keep:
                conversation_history.append({"role": "user", "content": user_input})

            # Prepare messages for OpenAI API
            messages = conversation_history if args.keep else [{"role": "user", "content": user_input}]

            # Call OpenAI API to get the shell command
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=messages,
                functions=[
                    {
                        "name": "execute_shell_command",
                        "description": "Execute a shell command and return the output",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "The shell command to execute"
                                }
                            },
                            "required": ["command"]
                        }
                    }
                ],
                function_call="auto"
            )

            # Check if a function call was made in the response
            if 'choices' in response and 'function_call' in response['choices'][0]['message']:
                function_call = response['choices'][0]['message']['function_call']
                
                # Parse the JSON string to a dictionary
                arguments = json.loads(function_call['arguments'])
                command_to_execute = arguments['command']
                
                # Ask for confirmation if -y flag is not set
                if not args.y:
                    confirmation = input(f"Do you want to execute the command: '{command_to_execute}'? (y/n): ")
                    if confirmation.lower() != 'y':
                        print_colored("Command execution cancelled.", 'YELLOW')
                        continue

                # Execute the command and get the output
                output = execute_shell_command(command_to_execute)

                # Print the output
                print_colored("\nCommand result:", 'GREEN')
                print(output)  # This will be printed in the default color

                # Add assistant's response and command output to conversation history if --keep is enabled
                if args.keep:
                    conversation_history.append({"role": "assistant", "content": f"Executed command: {command_to_execute}\nOutput: {output}"})
            else:
                # If no function call was made, print the OpenAI response
                print_colored("\nNo command to execute was generated.", 'YELLOW')
                print_colored("OpenAI response:", 'CYAN')
                if 'choices' in response and 'content' in response['choices'][0]['message']:
                    assistant_response = response['choices'][0]['message']['content']
                    print_colored(assistant_response, 'LIGHT_CYAN')  # Print OpenAI's text response in light cyan and bold
                    # Add assistant's response to conversation history if --keep is enabled
                    if args.keep:
                        conversation_history.append({"role": "assistant", "content": assistant_response})
                else:
                    print_colored("No text response available.", 'RED')

        except KeyboardInterrupt:
            continue
        except EOFError:
            break

if __name__ == "__main__":
    main()
