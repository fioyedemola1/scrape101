#!/bin/bash

# Configuration
TOTAL_RECORDS=1091
BATCH_SIZE=25
TOTAL_BATCHES=$(( (TOTAL_RECORDS + BATCH_SIZE - 1) / BATCH_SIZE ))  # Ceiling division

echo "Starting batch processing"
echo "Total Records: $TOTAL_RECORDS"
echo "Batch Size: $BATCH_SIZE"
echo "Total Batches: $TOTAL_BATCHES"

# Create a log directory if it doesn't exist
mkdir -p logs

# Run each batch
for ((i=0; i<TOTAL_BATCHES; i++))
do
    echo "=========================================="
    echo "Running batch $i of $((TOTAL_BATCHES-1))"
    echo "Start time: $(date)"
    
    # Run the batch and log output
    BATCH_INDEX=$i BATCH_SIZE=$BATCH_SIZE python run_batches.py 2>&1 | tee "logs/batch_${i}.log"
    
    # Check if the batch was successful
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "Batch $i completed successfully"
    else
        echo "Batch $i failed"
        echo "Check logs/batch_${i}.log for details"
    fi
    
    echo "End time: $(date)"
    echo "=========================================="
    
    # Wait between batches to prevent overwhelming the system
    if [ $i -lt $((TOTAL_BATCHES-1)) ]; then
        echo "Waiting 5 seconds before next batch..."
        sleep 5
    fi
done

echo "All batches completed"
echo "Check the logs directory for detailed output" 