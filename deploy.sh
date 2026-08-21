#!/bin/bash
#########################################
#   Script used by pipeline to deploy   #
#     to CKAN DEV/UAT environments      #
#########################################
#
# Tell the script to fail if any errors occur.
# For commands which we don't mind failing, we will add "|| true"
set -e
#
## Variables
#
EXT_NAME=ckanext-yukon
VENV=/usr/lib/ckan/default
#
###########################################

## Functions
#
function pull_latest_ckan_code {
        echo "Beginning code update process..."
        
        # Set permissions to allow pipeline user to run the deployment
        sudo chown -R jumpbox-pipelines:ckan $VENV/

        # Check to see if the extension directory exists or not
        if [ -d $VENV/src/$EXT_NAME ]; then
          echo "Extension directory exists."

          # Move into repository directory
          cd $VENV/src/$EXT_NAME/

          # Ensure the SSH remote is added to allow pipelines to pull code from BitBucket with key authentication (|| true added to avoid exiting on error if remote already exists)
          git remote add jumpbox-pipelines $BB_SSH_ORIGIN || true

          # Checkout the branch we are working with (in case somebody has been manually changing things)
          git checkout $BRANCH

          # Reset the repository in case, as above, manual changes have been made.
          git reset --hard
        else
          echo "Extension does not exist, cloning it..."

          cd $VENV/src/

          # Clone the repository
          git clone $BB_SSH_ORIGIN

          # Move into the new extension directory
          cd $VENV/src/$EXT_NAME/

          # Checkout the branch we are working with (in case somebody has been manually changing things)
          git checkout $BRANCH
        fi

        # Pull the latest code
        git pull jumpbox-pipelines $BRANCH
}

function run_make_process {
        echo "Beginning 'make' process for CKAN..."
        # Run make commands
        echo "Running 'make prepare' command..."
        make prepare
        echo "Running 'make full-upgrade' process..."
        make full-upgrade

        # Set ownership of CKAN virtual environment back to CKAN's user
        sudo chown -R ckan:ckan $VENV
}

echo "Beginning deployment to $INSTANCE_TYPE..."

# Add BitBucket key fingerprint to avoid connection issues later
ssh-keyscan bitbucket.org >> ~/.ssh/known_hosts

pull_latest_ckan_code
run_make_process

# Restart CKAN processes
case $INSTANCE_TYPE in
        SERVICES)
                # Run DB migrations
                echo "Running 'db upgrade' command..."
                $VENV/bin/ckan -c /etc/ckan/default/production.ini db upgrade

                # Restart CKAN worker process
                echo "Restarting the CKAN Worker process..."
                sudo supervisorctl restart ckan-worker:
                ;;
        WEB)
                # Restart CKAN uWSGI process
                echo "Restarting the CKAN uWSGI process..."
                sudo supervisorctl restart ckan-uwsgi:
                ;;
esac

echo "Deployment to $INSTANCE_TYPE complete."
