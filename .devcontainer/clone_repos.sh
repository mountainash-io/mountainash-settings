#!/bin/bash

# Function to clone and checkout branch with fallback
clone_and_checkout() {
    repo_name=$(basename "$2" .git)
    git clone "https://${CLONE_PRIVATE_REPOS_TOKEN}@github.com/$1/$2" "/workspaces/$repo_name"
    cd "/workspaces/$repo_name"
    
    if git branch -r | grep -q "origin/develop"; then
        git checkout develop
        echo "Checked out 'develop' branch in $repo_name"
    elif git branch -r | grep -q "origin/main"; then
        git checkout main
        echo "Warning: 'develop' branch not found in $repo_name. Checked out 'main' branch."
    else
        default_branch=$(git symbolic-ref --short HEAD)
        echo "Warning: Neither 'develop' nor 'main' branch found in $repo_name. Staying on default branch '$default_branch'."
    fi
    
    cd - > /dev/null
}

# List of repositories
repos=(
    # "mountainash-constants"
    # "mountainash-data"
    # "mountainash-datacontracts"
    # "mountainash-settings"
    # "mountainash-syntheticdata"
    # "mountainash-utils-dataclasses"
    # "mountainash-utils-factoryclasses"
    # "mountainash-utils-files"
    # "mountainash-utils-ssh"
    # "mountainash-utils-xml"
    # "mountainash-utils-gpg"
    # "mountainash-utils-hamilton"
    "mountainash-utils-os"
    # "mountainash-utils-rules"
    # "mountainash-acrds-constants"
    # "mountainash-acrds-settings"
    # "mountainash-acrds-core"
    # "mountainash-acrds-dagster"
    # "mountainash-acrds-syntheticdata"
    # "mountainash-acrds-datacontracts"
    # "mountainash-acrds-orchestration"
    # "mountainash-acrds-notebooks"
)

# Clone and checkout each repository
for repo in "${repos[@]}"; do
    clone_and_checkout "mountainash-io" "$repo.git"
done

echo "All repositories have been cloned and appropriate branches checked out."