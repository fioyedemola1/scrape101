#!/bin/bash

# Configuration
TOTAL_RECORDS=1000
BATCH_SIZE=25  # Changed to 25 URLs per batch
TOTAL_BATCHES=$((TOTAL_RECORDS / BATCH_SIZE))

# Function to run a single batch
run_batch() {
    local batch_index=$1
    local start_record=$((batch_index * BATCH_SIZE))
    local end_record=$((start_record + BATCH_SIZE - 1))
    echo "Running batch $batch_index (URLs $start_record-$end_record)"
    BATCH_INDEX=$batch_index BATCH_SIZE=$BATCH_SIZE docker-compose up --build
}

# Check if a specific batch index was provided
if [ ! -z "$1" ]; then
    if [ "$1" -ge 0 ] && [ "$1" -lt $TOTAL_BATCHES ]; then
        run_batch $1
    else
        echo "Invalid batch index. Must be between 0 and $((TOTAL_BATCHES - 1))"
        exit 1
    fi
else
    # Run all batches sequentially
    for ((i=0; i<TOTAL_BATCHES; i++)); do
        echo "Starting batch $i of $((TOTAL_BATCHES - 1))"
        run_batch $i
        echo "Batch $i completed"
        echo "----------------------------------------"
    done
fi 