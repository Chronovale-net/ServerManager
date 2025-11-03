#!/usr/bin/env python3
# Basic cat program

print("Ready!")

if __name__ == "__main__":
    while True:
        print("Enter a string: ", end="")
        lol = input()
        if lol == "exit":
            break
        print(lol)