package com.albidox.caching.config;

import java.nio.charset.StandardCharsets;
import java.util.BitSet;
import java.util.Collection;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.stereotype.Component;

/**
 * High performance probabilistic Bloom Filter for SKU existence validation.
 * Blocks cache penetration attacks by rejecting non-existent keys at the edge.
 */
@Component
public class SkuBloomFilter {

    private final int bitSetSize;
    private final int numHashFunctions;
    private final BitSet bitSet;
    private final AtomicLong insertedCount = new AtomicLong(0);
    private final AtomicLong checkCount = new AtomicLong(0);
    private final AtomicLong blockedCount = new AtomicLong(0);

    public SkuBloomFilter() {
        this(20_000, 0.01);
    }

    public SkuBloomFilter(int expectedInsertions, double falsePositiveProbability) {
        this.bitSetSize = optimalNumOfBits(expectedInsertions, falsePositiveProbability);
        this.numHashFunctions = optimalNumOfHashFunctions(expectedInsertions, this.bitSetSize);
        this.bitSet = new BitSet(this.bitSetSize);
    }

    public synchronized void add(String value) {
        if (value == null) {
            return;
        }
        int[] hashes = createHashes(value.getBytes(StandardCharsets.UTF_8), numHashFunctions, bitSetSize);
        for (int hash : hashes) {
            bitSet.set(hash);
        }
        insertedCount.incrementAndGet();
    }

    public synchronized void addAll(Collection<String> values) {
        if (values != null) {
            for (String val : values) {
                add(val);
            }
        }
    }

    public synchronized boolean mightContain(String value) {
        if (value == null) {
            return false;
        }
        checkCount.incrementAndGet();
        int[] hashes = createHashes(value.getBytes(StandardCharsets.UTF_8), numHashFunctions, bitSetSize);
        for (int hash : hashes) {
            if (!bitSet.get(hash)) {
                blockedCount.incrementAndGet();
                return false;
            }
        }
        return true;
    }

    public synchronized void clear() {
        bitSet.clear();
        insertedCount.set(0);
        checkCount.set(0);
        blockedCount.set(0);
    }

    public Map<String, Object> getMetrics() {
        return Map.of(
                "bitSetSize", bitSetSize,
                "numHashFunctions", numHashFunctions,
                "insertedCount", insertedCount.get(),
                "checkCount", checkCount.get(),
                "blockedCount", blockedCount.get()
        );
    }

    private static int optimalNumOfBits(long n, double p) {
        if (p == 0) {
            p = Double.MIN_VALUE;
        }
        return (int) (-n * Math.log(p) / (Math.log(2) * Math.log(2)));
    }

    private static int optimalNumOfHashFunctions(long n, long m) {
        return Math.max(1, (int) Math.round((double) m / n * Math.log(2)));
    }

    private static int[] createHashes(byte[] data, int hashes, int max) {
        int[] result = new int[hashes];
        int hash1 = murmur3(data, 0);
        int hash2 = murmur3(data, hash1);
        for (int i = 0; i < hashes; i++) {
            int combinedHash = hash1 + (i * hash2);
            if (combinedHash < 0) {
                combinedHash = ~combinedHash;
            }
            result[i] = combinedHash % max;
        }
        return result;
    }

    private static int murmur3(byte[] data, int seed) {
        int c1 = 0xcc9e2d51;
        int c2 = 0x1b873593;
        int h1 = seed;
        int len = data.length;
        int roundedEnd = (len & 0xfffffffc);

        for (int i = 0; i < roundedEnd; i += 4) {
            int k1 = (data[i] & 0xff) | ((data[i + 1] & 0xff) << 8) | ((data[i + 2] & 0xff) << 16) | (data[i + 3] << 24);
            k1 *= c1;
            k1 = (k1 << 15) | (k1 >>> 17);
            k1 *= c2;
            h1 ^= k1;
            h1 = (h1 << 13) | (h1 >>> 19);
            h1 = h1 * 5 + 0xe6546b64;
        }

        int k1 = 0;
        int tail = len & 0x03;
        if (tail == 3) {
            k1 ^= (data[roundedEnd + 2] & 0xff) << 16;
        }
        if (tail >= 2) {
            k1 ^= (data[roundedEnd + 1] & 0xff) << 8;
        }
        if (tail >= 1) {
            k1 ^= (data[roundedEnd] & 0xff);
            k1 *= c1;
            k1 = (k1 << 15) | (k1 >>> 17);
            k1 *= c2;
            h1 ^= k1;
        }

        h1 ^= len;
        h1 ^= (h1 >>> 16);
        h1 *= 0x85ebca6b;
        h1 ^= (h1 >>> 13);
        h1 *= 0xc2b2ae35;
        h1 ^= (h1 >>> 16);
        return h1;
    }
}
