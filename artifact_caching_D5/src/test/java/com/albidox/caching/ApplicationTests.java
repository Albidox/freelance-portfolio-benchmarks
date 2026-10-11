package com.albidox.caching;

import com.albidox.caching.config.CacheConfig;
import com.albidox.caching.dto.ProductDto;
import com.albidox.caching.dto.UpdateProductRequest;
import com.albidox.caching.service.ProductService;
import com.albidox.caching.exception.ResourceNotFoundException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class ApplicationTests {

    @Autowired
    private ProductService productService;

    @Autowired
    private CacheConfig.JacksonSerializedCacheManager cacheManager;

    @Autowired
    private ObjectMapper cachingObjectMapper;

    @BeforeEach
    void setUp() {
        productService.clearAllCaches();
        productService.setDbLatencyMs(0); // 0ms for fast deterministic test execution
    }

    @Test
    @DisplayName("Context loads successfully")
    void contextLoads() {
        assertNotNull(productService);
        assertNotNull(cacheManager);
        assertNotNull(cachingObjectMapper);
    }

    @Test
    @DisplayName("Cache hit avoids redundant database lookups")
    void testCacheHitReducesDbQueries() {
        String sku = "PROD-00001";

        long initialQueries = productService.getDbQueryCount();
        ProductDto cold = productService.getBySku(sku);
        assertNotNull(cold);
        assertEquals(sku, cold.sku());
        assertEquals(initialQueries + 1, productService.getDbQueryCount());

        // Second call should hit the Jackson-serialized cache
        ProductDto warm = productService.getBySku(sku);
        assertNotNull(warm);
        assertEquals(sku, warm.sku());
        assertEquals(initialQueries + 1, productService.getDbQueryCount(), "Database query count must not increase on cache hit");

        CacheConfig.JacksonSerializedCache cache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        var metrics = cache.getMetrics();
        assertTrue((Long) metrics.get("hitCount") >= 1);
    }

    @Test
    @DisplayName("Cache eviction invalidates stale data on update")
    void testCacheEvictionOnUpdate() {
        String sku = "PROD-00002";

        ProductDto original = productService.getBySku(sku);
        assertNotNull(original);

        BigDecimal updatedPrice = new BigDecimal("499.95");
        UpdateProductRequest updateReq = new UpdateProductRequest(
                "Updated Enterprise Cloud Module 2",
                "Updated description for testing cache eviction",
                "Compute",
                updatedPrice,
                120
        );

        ProductDto updated = productService.updateProduct(sku, updateReq);
        assertEquals(updatedPrice, updated.price());

        // Subsequent lookup must load fresh data
        ProductDto fetchedAfterEviction = productService.getBySku(sku);
        assertEquals(updatedPrice, fetchedAfterEviction.price());
        assertEquals("Updated Enterprise Cloud Module 2", fetchedAfterEviction.name());
    }

    @Test
    @DisplayName("Null values are not cached in products cache when null caching is disabled")
    void testNullCachingDisabled() {
        CacheConfig.JacksonSerializedCache cache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        cache.put("NULL-KEY", null);

        var wrapper = cache.get("NULL-KEY");
        assertNull(wrapper, "Null value must not be stored in cache when null caching is disabled");
    }

    @Test
    @DisplayName("Cache stampede defense: 500 concurrent threads hit expired key resulting in exactly 1 DB query")
    void testCacheStampedeMutexDefenseConcurrently() throws Exception {
        String sku = "PROD-00003";

        // Pre-warm the cache and verify initial query
        ProductDto initial = productService.getBySku(sku);
        assertNotNull(initial);

        // Force-expire the hot key
        productService.evictSku(sku);
        productService.resetDbQueryCount();

        int concurrency = 500;
        ExecutorService executor = Executors.newFixedThreadPool(32);
        try {
            List<Callable<ProductDto>> tasks = new ArrayList<>();
            for (int i = 0; i < concurrency; i++) {
                tasks.add(() -> productService.getBySku(sku, true, false, false));
            }

            List<Future<ProductDto>> futures = executor.invokeAll(tasks);
            for (Future<ProductDto> f : futures) {
                ProductDto result = f.get();
                assertNotNull(result);
                assertEquals(sku, result.sku());
            }

            // Distributed mutex locking must guarantee exactly 1 DB query
            assertEquals(1, productService.getDbQueryCount(),
                    "Cache stampede mutex defense failed: Expected exactly 1 DB query for 500 concurrent callers, got: "
                            + productService.getDbQueryCount());
        } finally {
            executor.shutdown();
        }
    }

    @Test
    @DisplayName("Cache penetration protection: Negative caching absorbs repeated non-existent queries")
    void testCachePenetrationNegativeCachingDefense() {
        productService.resetDbQueryCount();
        int nonExistentKeysCount = 100;
        List<String> nonExistentKeys = new ArrayList<>();
        for (int i = 1; i <= nonExistentKeysCount; i++) {
            nonExistentKeys.add(String.format("NONEXISTENT-TEST-%04d", i));
        }

        // Pass 1: Initial attack waves query DB and populate negative cache with 60s TTL
        for (String sku : nonExistentKeys) {
            assertThrows(ResourceNotFoundException.class, () ->
                    productService.getBySku(sku, true, true, false)
            );
        }
        long queriesAfterPass1 = productService.getDbQueryCount();
        assertEquals(nonExistentKeysCount, queriesAfterPass1, "Pass 1 should query DB for each unknown key");

        // Pass 2: Repeated penetration attack must be absorbed 100% by negative cache
        for (String sku : nonExistentKeys) {
            assertThrows(ResourceNotFoundException.class, () ->
                    productService.getBySku(sku, true, true, false)
            );
        }
        long queriesAfterPass2 = productService.getDbQueryCount();
        assertEquals(queriesAfterPass1, queriesAfterPass2,
                "Negative caching failed: DB query count increased on repeat queries for non-existent keys");
    }

    @Test
    @DisplayName("Cache penetration protection: Bloom filter blocks 100% of non-existent keys at the edge")
    void testCachePenetrationBloomFilterDefense() {
        productService.resetDbQueryCount();
        int attackKeysCount = 100;

        for (int i = 1; i <= attackKeysCount; i++) {
            String fakeSku = String.format("ATTACK-RANDOM-SKU-%04d", i);
            assertThrows(ResourceNotFoundException.class, () ->
                    productService.getBySku(fakeSku, true, false, true)
            );
        }

        assertEquals(0, productService.getDbQueryCount(),
                "Bloom filter failed to guard DB: Queries reached the persistent store");
    }

    @Test
    @DisplayName("Serialization compatibility: Jackson handles backward-compatible deserialization and schema evolution")
    void testJacksonSerializationBackwardCompatibilityAndEvolution() throws Exception {
        // Scenario A: v1 JSON payload without new field "manufacturer"
        String v1Json = """
                {
                  "id": 9001,
                  "sku": "EVOLVE-001",
                  "name": "Legacy Cloud Unit",
                  "description": "Payload serialized before manufacturer field was added",
                  "category": "Compute",
                  "price": 349.99,
                  "stockQuantity": 75,
                  "createdAt": "2026-10-11T00:00:00Z",
                  "updatedAt": "2026-10-11T00:00:00Z"
                }
                """;

        ProductDto deserializedV1 = cachingObjectMapper.readValue(v1Json, ProductDto.class);
        assertNotNull(deserializedV1);
        assertEquals(9001L, deserializedV1.id());
        assertEquals("EVOLVE-001", deserializedV1.sku());
        assertEquals("Legacy Cloud Unit", deserializedV1.name());
        assertNull(deserializedV1.manufacturer(), "Missing evolved field should deserialize as null without failure");

        // Scenario B: v3 JSON payload with extraneous/unknown fields (forward compatibility)
        String v3Json = """
                {
                  "id": 9002,
                  "sku": "EVOLVE-002",
                  "name": "Next-Gen Quantum Unit",
                  "description": "Payload with future fields",
                  "category": "Quantum",
                  "price": 1299.00,
                  "stockQuantity": 10,
                  "createdAt": "2026-10-11T00:00:00Z",
                  "updatedAt": "2026-10-11T00:00:00Z",
                  "manufacturer": "Future Systems Ltd",
                  "experimentalFeature": true,
                  "complianceGrade": "SOC2-TYPE2",
                  "tags": ["quantum", "sub-zero"]
                }
                """;

        ProductDto deserializedV3 = cachingObjectMapper.readValue(v3Json, ProductDto.class);
        assertNotNull(deserializedV3);
        assertEquals(9002L, deserializedV3.id());
        assertEquals("Future Systems Ltd", deserializedV3.manufacturer());

        // Scenario C: Round-trip cache payload verification
        CacheConfig.JacksonSerializedCache cache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        cache.put("EVOLVE-002", deserializedV3);
        var cached = cache.get("EVOLVE-002");
        assertNotNull(cached);
        ProductDto roundTrip = (ProductDto) cached.get();
        assertNotNull(roundTrip);
        assertEquals("Future Systems Ltd", roundTrip.manufacturer());
    }
}
