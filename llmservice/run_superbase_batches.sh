#!/bin/bash

# Configuration
TOTAL_RECORDS=940  # Updated to match actual number of records
BATCH_SIZE=25  # Number of records per batch
TOTAL_BATCHES=$(( (TOTAL_RECORDS + BATCH_SIZE - 1) / BATCH_SIZE ))  # Ceiling division
MAX_PARALLEL=8  # Maximum number of parallel processes

# Function to run a single batch
run_batch() {
    local batch_index=$1
    local start_record=$((batch_index * BATCH_SIZE))
    local end_record=$((start_record + BATCH_SIZE - 1))
    echo "Starting batch $batch_index (Records $start_record-$end_record)"
    
    # Run superbase.py with the specific batch range
    python3 "superbase.py" --start $start_record --end $end_record
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