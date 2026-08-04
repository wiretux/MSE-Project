import hashlib


def hamming_distance(a: bytes, b: bytes) -> int:
    a, b = int.from_bytes(a, "big"), int.from_bytes(b, "big")
    return bin(a ^ b).count("1")


def sim_hash(tokens: list[str]) -> int:
    # Define the hash Lenght
    hashLength = 64

    # Initialize the summed weights vector
    summedWeights = [0] * hashLength

    # Split into smaller chunkes for more precise detection
    chunkSize = 3
    chunks = []
    for token in tokens:
        if len(token) <= chunkSize:
            chunks.append(token)
        else:
            chunks.extend(
                [token[i : i + chunkSize] for i in range(len(token) - chunkSize + 1)]
            )

    # Compute Weights
    weightedMap = {}
    for chunk in chunks:
        weightedMap[chunk] = weightedMap.get(chunk, 0) + 1

    # Summing the weights
    for chunk, count in weightedMap.items():
        # Hashing the chunk
        hash_bytes = hashlib.md5(chunk.encode("utf-8")).digest()
        chunk_hash = int.from_bytes(hash_bytes[:8], byteorder="big")

        # Loop through each bit
        for i in range(hashLength):
            # Shift the hash to the currentBit
            currentBit = (chunk_hash >> i) & 1
            # Change the range from 0-1 to -1-1
            value = -1 + 2 * currentBit

            summedWeights[i] += count * value

    bit_list = [1 if bit > 0 else 0 for bit in summedWeights]

    final_int = 0
    for bit in bit_list:
        final_int = (final_int << 1) | bit
    return final_int
