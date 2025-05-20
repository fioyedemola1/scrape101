#!/bin/bash

# Configuration
TOTAL_RECORDS=940  # Updated to match actual number of records
BATCH_SIZE=25  # Number of records per batch
TOTAL_BATCHES=$(( (TOTAL_RECORDS + BATCH_SIZE - 1) / BATCH_SIZE ))  # Ceiling division
MAX_PARALLEL=1  # Maximum number of parallel processes

# Host configuration
# HOSTS=(
#     "https://6895-35-240-135-62.ngrok-free.app"
#     "https://159.203.3.54"
#     "https://your-third-host.com"  # Replace with your third host
# )
HOSTS=(
    "https://dcd1c083b621a4f5895d19cd862ea3dfb.clg07azjl.paperspacegradient.com/"
    # "https://159.203.3.54"
    # "https://your-third-host.com"  # Replace with your third host
)
HOST_COUNT=${#HOSTS[@]}

# Function to get next host in rotation
get_next_host() {
    local batch_index=$1
    local host_index=$((batch_index % HOST_COUNT))
    echo "${HOSTS[$host_index]}"
}

# Function to run a single batch
run_batch() {
    local batch_index=$1
    local start_record=$((batch_index * BATCH_SIZE))
    local end_record=$((start_record + BATCH_SIZE - 1))
    local host=$(get_next_host $batch_index)
    echo "Starting batch $batch_index (Records $start_record-$end_record) on host: $host"
    
    # Run superbase.py with the specific batch range and host
    python3 "superbase.py" --start $start_record --end $end_record --host "$host"
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
    # Run batches in parallel
    for ((i=0; i<TOTAL_BATCHES; i++)); do
        # Wait if we've reached max parallel processes
        while [ $(check_running_processes) -ge $MAX_PARALLEL ]; do
            sleep 5
        done
        
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