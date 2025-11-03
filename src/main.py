#!/usr/bin/env python3
from dotenv import load_dotenv

# load env variables

load_dotenv()

if __name__ == "__main__":
    print("Ready!")
    while True:
        print("Enter a string: ", end="")
        lol = input()
        if lol == "exit":
            break
        print(lol)
