#!/bin/bash

# Configuration
BATCH_SIZE=140     # Number of records per batch
TOTAL_BATCHES=3    # Exactly 3 batches
MAX_PARALLEL=3     # Maximum number of parallel processes (one per batch)

# Check if all required API keys are set
if [ -z "$GROQ_API_KEY_1" ] || [ -z "$GROQ_API_KEY_2" ] || [ -z "$GROQ_API_KEY_3" ]; then
    echo "Error: All three GROQ_API_KEY environment variables must be set"
    echo "Please set GROQ_API_KEY_1, GROQ_API_KEY_2, and GROQ_API_KEY_3"
    exit 1
fi

# HOSTS=(
#     # "https://da6ad0415251d49b1a76b134ba420d9eb.clg07azjl.paperspacegradient.com/"
#     "http://jjsa2mhwjzmxzjyninbpy8.llm.internal.aceso.no"
#     # "https://159.203.3.54"
#     # "https://your-third-host.com"  # Replace with your third host
# )
HOST_COUNT=${#HOSTS[@]}

# Function to get API key for specific batch
get_api_key() {
    local batch_index=$1
    case $batch_index in
        0) echo "$GROQ_API_KEY_1" ;;
        1) echo "$GROQ_API_KEY_2" ;;
        2) echo "$GROQ_API_KEY_3" ;;
        *) echo "Invalid batch index" >&2; exit 1 ;;
    esac
}

# Function to get next host in rotation
get_next_host() {
    local batch_index=$1
    local host_index=$((batch_index % HOST_COUNT))
    echo "${HOSTS[$host_index]}"
}

# Function to run a single batch
run_batch() {
    local batch_index=$1
    local api_key=$(get_api_key $batch_index)
    echo "Starting batch $batch_index"
    
    # Run superbase.py with the corresponding API key
    python3 "superbase.py" --token "$api_key"
    
    # # After superbase.py completes, run subcolumn.py with the same API key
    # echo "Starting sub-analysis for batch $batch_index"
    # python3 "subcolumn.py" --token "$api_key"
}

# Function to check running processes
check_running_processes() {
    local running=0
    for i in "${!pids[@]}"; do
        if [ -n "${pids[$i]}" ] && kill -0 "${pids[$i]}" 2>/dev/null; then
            ((running++))
        fi
    done
    echo $running
}

# Initialize array for process IDs
declare -a pids

# Check if a specific batch index was provided
if [ ! -z "$1" ]; then
    if [ "$1" -ge 0 ] && [ "$1" -lt $TOTAL_BATCHES ]; then
        run_batch "$1"
    else
        echo "Invalid batch index. Must be between 0 and $((TOTAL_BATCHES - 1))"
        exit 1
    fi
else
    # Run all three batches in parallel
    for ((i=0; i<TOTAL_BATCHES; i++)); do
        # Start new batch in background
        run_batch "$i" &
        pids[$i]=$!
        echo "Started batch $i (PID: ${pids[$i]})"
        sleep 2  # Small delay between starts to prevent resource contention
    done

    # Wait for all processes to complete
    echo "Waiting for all batches to complete..."
    for i in "${!pids[@]}"; do
        if [ -n "${pids[$i]}" ]; then
            wait "${pids[$i]}"
        fi
    done
    echo "All batches completed"
fi 