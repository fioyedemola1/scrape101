#!/bin/bash

# Configuration
TOTAL_RECORDS=940  # Updated to match actual number of records
BATCH_SIZE=25  # Number of records per batch
TOTAL_BATCHES=$(( (TOTAL_RECORDS + BATCH_SIZE - 1) / BATCH_SIZE ))  # Ceiling division
MAX_PARALLEL=8  # Maximum number of parallel processes
LOG_DIR="batch_logs"  # Directory for batch logs

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to run a single batch
run_batch() {
    local batch_index=$1
    local start_record=$((batch_index * BATCH_SIZE))
    local end_record=$((start_record + BATCH_SIZE - 1))
    local log_file="$LOG_DIR/batch_${batch_index}.log"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting batch $batch_index (Records $start_record-$end_record)" | tee -a "$log_file"
    
    # Run superbase.py with the specific batch range
    python3 "llm service/superbase.py" --start $start_record --end $end_record 2>&1 | tee -a "$log_file"
    
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch $batch_index failed with exit code $exit_code" | tee -a "$log_file"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch $batch_index completed successfully" | tee -a "$log_file"
    fi
}

# Function to check running processes
check_running_processes() {
    local running=0
    for i in "${!pids[@]}"; do
        if [ -n "${pids[$i]}" ] && kill -0 "${pids[$i]}" 2>/dev/null; then
            ((running++))
        else
            # Process is no longer running, check its log file
            local log_file="$LOG_DIR/batch_${i}.log"
            if [ -f "$log_file" ]; then
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch $i is no longer running. Check $log_file for details"
            fi
        fi
    done
    echo "$running"
}

# Initialize array for process IDs
declare -a pids

# Check if a specific batch index was provided
if [ -n "$1" ]; then
    if [ "$1" -ge 0 ] && [ "$1" -lt $TOTAL_BATCHES ]; then
        run_batch "$1"
    else
        echo "Invalid batch index. Must be between 0 and $((TOTAL_BATCHES - 1))"
        exit 1
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting parallel processing of $TOTAL_BATCHES batches"
    echo "Log files will be stored in $LOG_DIR/"
    
    # Run batches in parallel
    for ((i=0; i<TOTAL_BATCHES; i++)); do
        # Wait if we've reached max parallel processes
        while [ "$(check_running_processes)" -ge $MAX_PARALLEL ]; do
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for a slot to become available..."
            sleep 5
        done
        
        # Start new batch in background
        run_batch "$i" &
        pids[$i]=$!
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Started batch $i (PID: ${pids[$i]})"
        sleep 2  # Small delay between starts to prevent resource contention
    done

    # Wait for all processes to complete
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for all batches to complete..."
    for i in "${!pids[@]}"; do
        if [ -n "${pids[$i]}" ]; then
            wait "${pids[$i]}"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch $i finished"
        fi
    done
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] All batches completed"
fi 