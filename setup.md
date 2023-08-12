# MoveBot - Self hosting setup

On this page:

[[_TOC_]]

## Summary
Hosting the bot does not require significant resources and can be hosted on VM with ~128MiB of memory. Docker is a relatively straightforward way to host the bot without having to do much to your environment after the Docker setup is completed. MoveBot can be hosted on any host with an internet connection and Python3 interpreter.

## Setup your Discord application
MoveBot requires a Discord application to interact with your server. The following steps will guide you through this and should be completed before setting up the Python application in Docker or directly on a system.

1. Create an application on [Discord's developer portal](https://discord.com/developers/applications). You will require the application ID/client ID and the application token - both of these are obtainable from OAuth2 > General page.

2. The bot will require privileged gateway intents. Under the bot settings in the developer portal > bot > enable "server members intent" and "message content intent.

3. Invite the bot to your Discord server using a generated URL. In Discord's developer portal go to OAuth2 > URL Generator and enable the bot scope.
   The bot permissions required are:
      * General permissions:
        * Manage webhooks
        * Read messages/view channels
      * Test permissions:
        * Send messages
        * Send messages in threads
        * Manage messages
        * Embed links
        * Attach files
        * Read message history
        * Mention everyone
        * Use external emojis
        * Add reactions
        * Use slash commands

   Use the generated URL to invite the bot to your server. After inviting the bot assign any individual permissions or customise further with a nickname.


## Docker

When you have your docker environment setup and running complete the following.

1. Setup the Discord application as per the above instructions.

2. Clone the repository and build the docker container.

    ```bash
    git clone https://gitlab.com/sean.ms/movebot.git
    docker build -t discord-movebot .
    ```

3. Create the environment file to connect the app to your Discord server. 

    ```bash
    cat <<EOF > /path/to/your/.env
    DISCORD_TOKEN=<APPLICATION TOKEN HERE>
    LISTEN_TO=!mv 
    STATS_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0IjoxLCJpZCI6Ijg0Njg1MTc4MjA0NzMwMTcyMiIsImlhdCI6MTYyMjIyODY3MH0._wz_HHk3Ao3jDCAbQuxQ-Y9T0sQDwBdFfwNp7_OtTks
    ADMIN_UID=<YOUR DISCORD ID>
    MOVEBOT_ID=<APPLICATION ID/CLIENT ID>
    MOVEBOT_STATS_ID=<APPLICATION ID>
    LOG_PATH=movebot.log
    DB_PATH=settings.db
    EOF
    ```

    Notable environment variables:
      - DISCORD_TOKEN: This is the secret to allow the application to use Discord as the bot
      - ADMIN_UID: This should be your Discord ID and allows the bot to send you a DM tracking the number of servers it has joined.
      - MOVEBOT_ID: This is the application ID/client ID.
      - MOVEBOT_STATS_ID: This is the application ID/client ID.

4. Run MoveBot in Docker in the foreground. If there are any runtime errors they should be presented now.
    ```bash
    docker run -it --mount type=bind,source=/path/to/your/.env,target=/movebot/.env discord-movebot move_bot.py
    ```

5. Finally, run MoveBot in Docker in detached mode.
    ```bash
    docker run -d --mount type=bind,source=/path/to/your/.env,target=/movebot/.env discord-movebot move_bot.py
    ```

## Linux (deb/rpm)
Running the bot directly on Linux requires several simple steps to setup. The provided instructions will allow the bot to run as a system service and will output all messages to the standard system log files. The bot will run in the background once started and will automatically restart if systemd detects the process has exited unexpectedly.<br>
<br>

1. Setup the Discord application as per the above instructions.

2. Install Python3 and Pip3. Python 3.10 was installed in my Ubuntu 22.04.2 test environment and was working fine at the time of writing.

    For .deb packaging (Ubuntu/Debian):
    ```bash
    sudo apt update
    sudo apt install python3 python3-pip git
    ```

    For .rpm packaging (Redhat/Rocky Linux/AlmaLinux)
    ```bash
    sudo yum install python3 python3-pip git
    ```

3. Optional but recommended step. Create a dedicated Linux user account to run the bot as. The bot does not need priviledged access to your system and for security purposes it is much safer to run this as a standard user account. This will create a home directory we can use later for the bot.

    ```bash
    sudo useradd -m movebot
    ```

4. Obtain the code from Git and clone to your home directory or a more generic directory if you prefer. In my example, I switch to the movebot user and clone the Git repo using that.

    ```bash
    sudo su - movebot
    git clone https://gitlab.com/sean.ms/movebot.git
    ```
  
   This will clone the files to `/home/movebot/movebot`.

5. Next the environment file to connect the app to your Discord server must be setup. 

    ```bash
    cat <<EOF > /home/movebot/movebot/.env
    DISCORD_TOKEN=<APPLICATION TOKEN HERE>
    LISTEN_TO=!mv 
    STATS_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0IjoxLCJpZCI6Ijg0Njg1MTc4MjA0NzMwMTcyMiIsImlhdCI6MTYyMjIyODY3MH0._wz_HHk3Ao3jDCAbQuxQ-Y9T0sQDwBdFfwNp7_OtTks
    ADMIN_UID=<YOUR DISCORD ID>
    MOVEBOT_ID=<APPLICATION ID>
    MOVEBOT_STATS_ID=<APPLICATION ID>
    LOG_PATH=movebot.log
    DB_PATH=settings.db
    EOF
    ```

    Notable environment variables:
      - DISCORD_TOKEN: This is the secret to allow the application to use Discord as the bot
      - ADMIN_UID: This should be your Discord ID and allows the bot to send you a DM tracking the number of servers it has joined.
      - MOVEBOT_ID: This is the application ID/client ID.
      - MOVEBOT_STATS_ID: This is the application ID/client ID.

6. A systemd service file is present to copy to the system to require no further manual installation of files. This will run through the Python requirements to correctly setup the environment and then start the bot.

    ```bash
    sudo cp /home/movebot/movebot/discord-movebot.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now discord-movebot
    ```

7. If everything worked the service will have pulled all Python requirements and be in a running state. This can be checked in the log files and/or against systemd status.

   ```bash
   sudo systemctl status discord-movebot
   sudo journalctl -xeu discord-movebot
   ```

   If the service is constantly restarting there is likely an issue with your setup. Run the bot in the foreground as `/usr/bin/python3 /home/movebot/movebot/move_bot.py` to see any errors when the application doesn't run.
