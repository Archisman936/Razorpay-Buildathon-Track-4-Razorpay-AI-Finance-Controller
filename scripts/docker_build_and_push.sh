#!/usr/bin/env bash
set -e

USERNAME="${1:-archisman2006}"
TAG="${2:-latest}"

BACKEND_IMAGE="${USERNAME}/razorpay-backend:${TAG}"
FRONTEND_IMAGE="${USERNAME}/razorpay-frontend:${TAG}"

echo "===================================================="
echo " Building Docker Images"
echo " Backend : ${BACKEND_IMAGE}"
echo " Frontend: ${FRONTEND_IMAGE}"
echo "===================================================="

echo -e "\n[1/2] Building Backend Docker image..."
docker build -t "${BACKEND_IMAGE}" -f backend/Dockerfile .

echo -e "\n[2/2] Building Frontend Docker image..."
docker build -t "${FRONTEND_IMAGE}" -f frontend/Dockerfile ./frontend

echo -e "\nSuccessfully built both images!"

echo "===================================================="
echo " Pushing to Docker Hub"
echo "===================================================="

echo -e "\nPushing ${BACKEND_IMAGE}..."
docker push "${BACKEND_IMAGE}"

echo -e "\nPushing ${FRONTEND_IMAGE}..."
docker push "${FRONTEND_IMAGE}"

echo -e "\nSuccessfully pushed all images to Docker Hub!"
