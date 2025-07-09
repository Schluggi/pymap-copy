import subprocess
import os
import getpass

def get_input(prompt, hide=False):
    return getpass.getpass(prompt + ": ") if hide else input(prompt + ": ").strip()

def main():
    print("IMAP Mailbox Copier – Interactive Mode")

    old_server = get_input("Enter Old Server")
    old_email  = get_input("Enter Old Email")
    old_pass   = get_input("Enter Old Password", hide=True)

    new_server = get_input("Enter New Server")
    new_email  = get_input("Enter New Email")
    new_pass   = get_input("Enter New Password", hide=True)

    script_path = os.path.join(os.path.dirname(__file__), "pymap-copy.py")
    if not os.path.exists(script_path):
        print("Error: pymap-copy.py not found in this folder.")
        return

    command = [
        "python3", script_path,
        "-u", old_email, "-p", old_pass, "-s", old_server,
        "-U", new_email, "-P", new_pass, "-S", new_server
    ]

    print("\nRunning migration command...\n")

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='')  # stream output line by line

        process.wait()
        print(f"\nProcess exited with code {process.returncode}")
    except Exception as e:
        print("Error while running command:", e)

if __name__ == "__main__":
    main()
