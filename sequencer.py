import json
import requests
import csv
import os
import random
import string
import traceback
import shutil
import re
import time
from bs4 import BeautifulSoup
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set the local LLM API endpoint
api_url = "http://localhost:8080/v1/chat/completions"
api_headers = {"Content-Type": "application/json"}

# Load prompts from a single-column CSV file
def load_initial_prompts(file_path):
    if not os.path.exists(file_path):
        print(f"File '{file_path}' not found. Using default initial prompt: '.'")
        return ["."]
    
    with open(file_path, mode='r', encoding='utf-8') as file:
        content = file.read()
    
    segments = content.splitlines()
    return [segment.strip() for segment in segments if segment.strip()]

# Logging function to write results to a CSV file
def log_to_csv(log_file, step_number, prompt_name, formatted_prompt, response):
    file_exists = os.path.isfile(log_file)
    with open(log_file, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Step", "Prompt Name", "Formatted Prompt", "Response"])
        if not file_exists:
            writer.writeheader()
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
        reader = csv.DictReader(csvfile, delimiter='|')
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

        if action == "run_prompt_sequence":
            nested_sequence_file = prompt_info["Formatted Prompt"]
            if not nested_sequence_file:
                print(f"Missing 'Sequence File' for action 'run_prompt_sequence'.")
                break

            try:
                nested_sequence = load_prompt_sequence(nested_sequence_file)
                print(f"\nRunning nested sequence: {nested_sequence_file}")
                run_prompt_sequence(nested_sequence, formatted_prompt, log_file)
            except Exception as e:
                error_message = f"Error running nested sequence '{nested_sequence_file}': {e}"
                return error_message  # Return the error message as a string
        elif action in FUNCTION_REGISTRY:
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

        log_to_csv(log_file, step_number, current_prompt_name, formatted_prompt, llm_response)

        context[prompt_info["LLM Response"]] = llm_response

        if condition:
            try:
                condition_result = eval(condition, {}, context)
                print(f"Condition is '{condition}' within {context} and resulted in value: {condition_result}")
                current_prompt_name = true_next_prompt if condition_result else false_next_prompt
            except Exception as e:
                print(f"Error evaluating condition '{condition}': {e}")
                break
        else:
            current_prompt_name = next_prompt_name if next_prompt_name != "stop" else None

        step_number += 1

# File handler for Watchdog
class FunctionFileHandler(FileSystemEventHandler):
    def __init__(self, file_path):
        self.file_path = file_path

    def on_modified(self, event):
        if event.src_path.endswith(self.file_path):
            print("\nDetected changes in 'functions.json'. Reloading functions...")
            global FUNCTION_REGISTRY
            function_code = load_functions(self.file_path)
            FUNCTION_REGISTRY = define_functions(function_code)
            FUNCTION_REGISTRY["run_prompt_sequence"] = run_prompt_sequence

# Modify the start_watcher function to ensure absolute paths are used
def start_watcher(file_path):
    file_dir = os.path.dirname(file_path)  # Get the directory of the file
    if not os.path.exists(file_dir):
        print(f"Directory {file_dir} does not exist. Please check the path.")
        return None

    event_handler = FunctionFileHandler(file_path)
    observer = Observer()
    observer.schedule(event_handler, path=file_dir, recursive=False)  # Watch the directory containing the file
    observer.start()
    return observer

# Ensure you pass the correct path for functions.json
file_path_functions = os.path.abspath("functions.json")  # Get absolute path to avoid relative path issues
observer = start_watcher(file_path_functions)

# Main setup
file_path_functions = "C:\\Users\\dbddv\\gptfactory\\functions.json"
function_code = load_functions(file_path_functions)
FUNCTION_REGISTRY = define_functions(function_code)
FUNCTION_REGISTRY["run_prompt_sequence"] = run_prompt_sequence

# Start the file watcher
observer = start_watcher(file_path_functions)

# Load dataset and run for each initial prompt
initial_prompts_file = "initial_prompts.txt"
initial_prompts = load_initial_prompts(initial_prompts_file)

sequence_file = "Main_sequence.csv"
prompt_sequence = load_prompt_sequence(sequence_file)

try:
    for initial_prompt in initial_prompts:
        print(f"\nRunning sequence for initial prompt: {initial_prompt}")
        print("=" * 50)
        run_prompt_sequence(prompt_sequence, initial_prompt, log_file="sequence_log.csv")
        print("=" * 50)
finally:
    observer.stop()
    observer.join()




