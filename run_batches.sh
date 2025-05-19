#!/bin/bash

# Configuration
TOTAL_RECORDS=1091  # Updated to match actual number of URLs in Buyers.csv
BATCH_SIZE=25  # Changed to 25 URLs per batch
TOTAL_BATCHES=$(( (TOTAL_RECORDS + BATCH_SIZE - 1) / BATCH_SIZE ))  # Use ceiling division
MAX_PARALLEL=8  # Maximum number of parallel processes

# Function to run a single batch
run_batch() {
    local batch_index=$1
    local start_record=$((batch_index * BATCH_SIZE))
    local end_record=$((start_record + BATCH_SIZE - 1))
    echo "Starting batch $batch_index (URLs $start_record-$end_record)"
    BATCH_INDEX=$batch_index BATCH_SIZE=$BATCH_SIZE docker compose up --build
    # Remove the container after the batch is done
    docker compose rm -f scrape101-scraper-$batch_index
}

# Function to check running processes
check_running_processes() {
    local running=0
    for pid in "${pids[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            ((running++))
        fi
    done
    echo $running
}

# Array to store process IDs
declare -a pids

# Check if a specific batch index was provided
if [ ! -z "$1" ]; then
    if [ "$1" -ge 0 ] && [ "$1" -lt $TOTAL_BATCHES ]; then
        run_batch $1
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
        run_batch $i &
        pids+=($!)
        echo "Started batch $i (PID: ${pids[-1]})"
        sleep 2  # Small delay between starts to prevent resource contention
    done

    # Wait for all processes to complete
    echo "Waiting for all batches to complete..."
    for pid in "${pids[@]}"; do
        wait $pid
    done
    echo "All batches completed"
fi 