package com.albidox.caching.service;

import com.albidox.caching.config.CacheConfig;
import com.albidox.caching.config.KeyMutexLockManager;
import com.albidox.caching.config.SkuBloomFilter;
import com.albidox.caching.dto.ProductDto;
import com.albidox.caching.dto.UpdateProductRequest;
import com.albidox.caching.entity.Product;
import com.albidox.caching.exception.ResourceNotFoundException;
import com.albidox.caching.repository.ProductRepository;
import jakarta.annotation.PostConstruct;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.Cache;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProductService {

    private static final Logger log = LoggerFactory.getLogger(ProductService.class);

    private final ProductRepository productRepository;
    private final CacheConfig.JacksonSerializedCacheManager cacheManager;
    private final KeyMutexLockManager mutexLockManager;
    private final SkuBloomFilter bloomFilter;

    private final AtomicLong dbQueryCount = new AtomicLong(0);

    @Value("${app.simulation.db-latency-ms:50}")
    private long dbLatencyMs;

    public ProductService(
            ProductRepository productRepository,
            CacheConfig.JacksonSerializedCacheManager cacheManager,
            KeyMutexLockManager mutexLockManager,
            SkuBloomFilter bloomFilter
    ) {
        this.productRepository = productRepository;
        this.cacheManager = cacheManager;
        this.mutexLockManager = mutexLockManager;
        this.bloomFilter = bloomFilter;
    }

    @PostConstruct
    public void initializeBloomFilter() {
        try {
            List<String> skus = productRepository.findAllSkus();
            bloomFilter.addAll(skus);
            log.info("Initialized SKU Bloom Filter with {} catalog entries", skus.size());
        } catch (Exception e) {
            log.warn("Could not pre-seed Bloom filter on startup: {}", e.getMessage());
        }
    }

    public ProductDto getBySku(String sku) {
        return getBySku(sku, true, true, false);
    }

    @Transactional(readOnly = true)
    public ProductDto getBySku(String sku, boolean useMutex, boolean useNegativeCache, boolean useBloomFilter) {
        if (sku == null || sku.isBlank()) {
            throw new ResourceNotFoundException("Product SKU cannot be blank");
        }

        // 1. Bloom Filter defense: reject guaranteed non-existent keys at the edge
        if (useBloomFilter && !bloomFilter.mightContain(sku)) {
            log.debug("Bloom filter blocked non-existent SKU: {}", sku);
            throw new ResourceNotFoundException("Product not found with SKU (blocked by Bloom filter): " + sku);
        }

        CacheConfig.JacksonSerializedCache productsCache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        CacheConfig.JacksonSerializedCache negativeCache = cacheManager.getCustomCache(CacheConfig.CACHE_NEGATIVE);

        // 2. Negative cache check: return cached 404 sentinel if previously missed
        if (useNegativeCache) {
            Cache.ValueWrapper negWrapper = negativeCache.get(sku);
            if (negWrapper != null && negWrapper.get() != null) {
                log.debug("Negative cache hit for SKU: {}", sku);
                throw new ResourceNotFoundException("Product not found with SKU (cached negative entry): " + sku);
            }
        }

        // 3. Hot cache check
        Cache.ValueWrapper cached = productsCache.get(sku);
        if (cached != null && cached.get() != null) {
            return (ProductDto) cached.get();
        }

        // 4. Cache Miss: Mutex Locking vs Unprotected Path
        if (useMutex) {
            mutexLockManager.acquire(sku);
            try {
                // Double-checked negative cache
                if (useNegativeCache) {
                    Cache.ValueWrapper negWrapper = negativeCache.get(sku);
                    if (negWrapper != null && negWrapper.get() != null) {
                        throw new ResourceNotFoundException("Product not found with SKU (cached negative entry): " + sku);
                    }
                }

                // Double-checked products cache
                Cache.ValueWrapper doubleCheck = productsCache.get(sku);
                if (doubleCheck != null && doubleCheck.get() != null) {
                    return (ProductDto) doubleCheck.get();
                }

                // Single winner executes persistent database query
                return executeDbLookupAndCache(sku, productsCache, negativeCache, useNegativeCache);
            } finally {
                mutexLockManager.release(sku);
            }
        } else {
            // Unprotected probe path: bypasses mutex lock (demonstrates thundering herd)
            return executeDbLookupAndCache(sku, productsCache, negativeCache, useNegativeCache);
        }
    }

    private ProductDto executeDbLookupAndCache(
            String sku,
            CacheConfig.JacksonSerializedCache productsCache,
            CacheConfig.JacksonSerializedCache negativeCache,
            boolean useNegativeCache
    ) {
        dbQueryCount.incrementAndGet();
        simulateDatabaseProcessingLatency();

        Optional<Product> optional = productRepository.findBySku(sku);
        if (optional.isEmpty()) {
            if (useNegativeCache) {
                // Cache null sentinel with 60-second TTL
                negativeCache.put(sku, ProductDto.nullSentinel(sku));
            }
            throw new ResourceNotFoundException("Product not found with SKU: " + sku);
        }

        Product product = optional.get();
        ProductDto dto = toDto(product);
        productsCache.put(sku, dto);
        return dto;
    }

    @Transactional
    public ProductDto updateProduct(String sku, UpdateProductRequest request) {
        dbQueryCount.incrementAndGet();

        Product product = productRepository.findBySku(sku)
                .orElseThrow(() -> new ResourceNotFoundException("Product not found with SKU: " + sku));

        if (request.name() != null) {
            product.setName(request.name());
        }
        if (request.description() != null) {
            product.setDescription(request.description());
        }
        if (request.category() != null) {
            product.setCategory(request.category());
        }
        if (request.price() != null) {
            product.setPrice(request.price());
        }
        if (request.stockQuantity() != null) {
            product.setStockQuantity(request.stockQuantity());
        }
        product.setUpdatedAt(OffsetDateTime.now());

        Product saved = productRepository.save(product);

        // Evict from caches upon update
        CacheConfig.JacksonSerializedCache productsCache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        CacheConfig.JacksonSerializedCache negativeCache = cacheManager.getCustomCache(CacheConfig.CACHE_NEGATIVE);
        productsCache.evict(sku);
        negativeCache.evict(sku);
        bloomFilter.add(sku);

        log.info("Product updated and cache evicted for SKU: {}", sku);
        return toDto(saved);
    }

    public void evictSku(String sku) {
        CacheConfig.JacksonSerializedCache productsCache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        CacheConfig.JacksonSerializedCache negativeCache = cacheManager.getCustomCache(CacheConfig.CACHE_NEGATIVE);
        productsCache.evict(sku);
        negativeCache.evict(sku);
    }

    public void clearAllCaches() {
        CacheConfig.JacksonSerializedCache productsCache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        CacheConfig.JacksonSerializedCache negativeCache = cacheManager.getCustomCache(CacheConfig.CACHE_NEGATIVE);
        productsCache.clear();
        negativeCache.clear();
        mutexLockManager.clear();
        resetDbQueryCount();
    }

    public Map<String, Object> getBloomFilterMetrics() {
        return bloomFilter.getMetrics();
    }

    public void reseedBloomFilter() {
        bloomFilter.clear();
        initializeBloomFilter();
    }

    public long getDbQueryCount() {
        return dbQueryCount.get();
    }

    public void resetDbQueryCount() {
        dbQueryCount.set(0);
    }

    public void setDbLatencyMs(long ms) {
        this.dbLatencyMs = ms;
    }

    public long getDbLatencyMs() {
        return this.dbLatencyMs;
    }

    private void simulateDatabaseProcessingLatency() {
        if (dbLatencyMs > 0) {
            try {
                Thread.sleep(dbLatencyMs);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private ProductDto toDto(Product p) {
        return new ProductDto(
                p.getId(),
                p.getSku(),
                p.getName(),
                p.getDescription(),
                p.getCategory(),
                p.getPrice(),
                p.getStockQuantity(),
                p.getCreatedAt(),
                p.getUpdatedAt(),
                p.getManufacturer()
        );
    }
}
