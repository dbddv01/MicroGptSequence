import json
import requests
import csv
import os
import random
import string
import traceback
from bs4 import BeautifulSoup
# Set the local LLM API endpoint
api_url = "http://localhost:8080/v1/chat/completions"
api_headers = {"Content-Type": "application/json"}

# Load prompts from a single-column CSV file
def load_initial_prompts(file_path):
    if not os.path.exists(file_path):
        print(f"File '{file_path}' not found. Using default initial prompt: '.'")
        return ["."]
    
    with open(file_path, mode='r', encoding='utf-8') as file:
        content = file.read()  # Read the entire file as a single string
    
    # Split the content into segments based on line breaks
    segments = content.splitlines()
    return [segment.strip() for segment in segments if segment.strip()]  # Remove empty lines and extra spaces


# Logging function to write results to a CSV file
def log_to_csv(log_file, step_number, prompt_name, formatted_prompt, response):
    file_exists = os.path.isfile(log_file)
    with open(log_file, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Step", "Prompt Name", "Formatted Prompt", "Response"])
        if not file_exists:
            writer.writeheader()  # Write header only if file does not exist
        writer.writerow({
            "Step": step_number,
            "Prompt Name": prompt_name,
            "Formatted Prompt": formatted_prompt,
            "Response": response
        })

# Load function code from a file
def load_functions(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        functions = json.load(file)
    return functions

# Define the functions dynamically
def define_functions(functions):
    local_namespace = {}
    for name, code in functions.items():
        exec(code, globals(), local_namespace)
    return local_namespace

# Load structured sequence
def load_prompt_sequence(file_path):
    sequence = {}
    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter='|')  # Specify the '|' delimiter
        for row in reader:
            sequence[row['Prompt Name']] = row
    return sequence

# Modify run_prompt_sequence to handle nested sequences
def run_prompt_sequence(sequence, initial_prompt, log_file="sequence_log.csv"):
    context = {"InitialPrompt": initial_prompt}
    current_prompt_name = "Start"
    step_number = 1

    while current_prompt_name:
        prompt_info = sequence[current_prompt_name]
        prompt_template = prompt_info["Formatted Prompt"]
        action = prompt_info["Action"]
        condition = prompt_info.get("Condition", None)
        true_next_prompt = prompt_info.get("True Next Prompt", None)
        false_next_prompt = prompt_info.get("False Next Prompt", None)
        next_prompt_name = prompt_info.get("Next Prompt", None)

        formatted_prompt = prompt_template.format(**context)

        # Check if action is to run another sequence
        if action == "run_prompt_sequence":
            nested_sequence_file = prompt_info.get("Sequence File")
            if not nested_sequence_file:
                print(f"Missing 'Sequence File' for action 'run_prompt_sequence'.")
                break

            try:
                # Load the nested sequence
                nested_sequence = load_prompt_sequence(nested_sequence_file)
                print(f"\nRunning nested sequence: {nested_sequence_file}")
                run_prompt_sequence(nested_sequence, formatted_prompt, log_file)  # Recursive call
            except Exception as e:
                print(f"Error running nested sequence '{nested_sequence_file}': {e}")
                break
        elif action in FUNCTION_REGISTRY:
            # Call a registered function
            llm_response = FUNCTION_REGISTRY[action](formatted_prompt)
        else:
            print(f"Action '{action}' not recognized.")
            break

        print(f"\n{'*' * 40}")
        print(f"Step {step_number}")
        print(f"{'-' * 40}")
        print(f"Prompt:\n{formatted_prompt}")
        print(f"{'-' * 40}")
        print(f"Response:\n{llm_response}")
        print(f"{'*' * 40}\n")

        # Log the prompt and response
        log_to_csv(log_file, step_number, current_prompt_name, formatted_prompt, llm_response)

        context[prompt_info["LLM Response"]] = llm_response

        # Evaluate condition
        if condition:
            try:
                condition_result = eval(condition, {}, context)
                print(f"Condition is '{condition} within {context} and resulted in value : {condition_result}'")
                current_prompt_name = true_next_prompt if condition_result else false_next_prompt
            except Exception as e:
                print(f"Error evaluating condition '{condition}': {e}")
                break
        else:
            current_prompt_name = next_prompt_name if next_prompt_name != "stop" else None

        step_number += 1

# Load function definitions
file_path_functions = "functions.json"
function_code = load_functions(file_path_functions)
FUNCTION_REGISTRY = define_functions(function_code)
FUNCTION_REGISTRY["run_prompt_sequence"] = run_prompt_sequence  # Add it to the registry

# Load dataset and run for each initial prompt
initial_prompts_file = "initial_prompts.txt"
initial_prompts = load_initial_prompts(initial_prompts_file)

sequence_file = "table_data.csv"
prompt_sequence = load_prompt_sequence(sequence_file)

# Run the sequence for each initial prompt
for initial_prompt in initial_prompts:
    print(f"\nRunning sequence for initial prompt: {initial_prompt}")
    print("=" * 50)
    run_prompt_sequence(prompt_sequence, initial_prompt, log_file="sequence_log.csv")
    print("=" * 50)

