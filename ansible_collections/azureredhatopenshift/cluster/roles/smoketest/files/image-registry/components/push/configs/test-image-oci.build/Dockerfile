# SPDX-License-Identifier: Apache-2.0
# github.com/cloudygreybeard, 2025

# Step 1: Build the binary in a container using musl
FROM alpine:latest as builder

# Install build dependencies (including musl)
RUN apk add --no-cache build-base musl-dev

# Set the working directory
WORKDIR /src

# Copy the C source code into the container
COPY hello.c .

# Compile the C program using musl for a minimal binary
RUN gcc -Os -static -o hello hello.c

# Strip the binary to remove unnecessary debug symbols and reduce size
RUN strip --strip-all hello

# Step 2: Create a minimal image to run the program
FROM scratch

# Copy the statically linked and stripped binary from the builder stage
COPY --from=builder /src/hello /hello

# Command to run the program
CMD ["/hello"]

