package com.albidox.caching.controller;

import com.albidox.caching.config.CacheConfig;
import com.albidox.caching.dto.ProductDto;
import com.albidox.caching.dto.UpdateProductRequest;
import com.albidox.caching.service.ProductService;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/products")
public class ProductController {

    private final ProductService productService;
    private final CacheConfig.JacksonSerializedCacheManager cacheManager;

    public ProductController(ProductService productService, CacheConfig.JacksonSerializedCacheManager cacheManager) {
        this.productService = productService;
        this.cacheManager = cacheManager;
    }

    @GetMapping("/{sku}")
    public ResponseEntity<ProductDto> getProductBySku(
            @PathVariable String sku,
            @RequestParam(defaultValue = "true") boolean mutex,
            @RequestParam(defaultValue = "true") boolean negativeCache,
            @RequestParam(defaultValue = "false") boolean bloomFilter) {
        ProductDto dto = productService.getBySku(sku, mutex, negativeCache, bloomFilter);
        return ResponseEntity.ok(dto);
    }

    @PostMapping("/cache/evict/{sku}")
    public ResponseEntity<Map<String, String>> evictSku(@PathVariable String sku) {
        productService.evictSku(sku);
        return ResponseEntity.ok(Map.of("sku", sku, "status", "Evicted from products and negative caches"));
    }

    @PutMapping("/{sku}")
    public ResponseEntity<ProductDto> updateProduct(
            @PathVariable String sku,
            @RequestBody UpdateProductRequest request) {
        ProductDto updated = productService.updateProduct(sku, request);
        return ResponseEntity.ok(updated);
    }

    @GetMapping("/cache/stats")
    public ResponseEntity<Map<String, Object>> getCacheStats() {
        CacheConfig.JacksonSerializedCache productsCache = cacheManager.getCustomCache(CacheConfig.CACHE_PRODUCTS);
        CacheConfig.JacksonSerializedCache negativeCache = cacheManager.getCustomCache(CacheConfig.CACHE_NEGATIVE);
        return ResponseEntity.ok(Map.of(
                "metrics", productsCache.getMetrics(),
                "negativeMetrics", negativeCache.getMetrics(),
                "dbQueryCount", productService.getDbQueryCount(),
                "dbLatencyMs", productService.getDbLatencyMs(),
                "bloomFilter", productService.getBloomFilterMetrics()
        ));
    }

    @PostMapping("/cache/clear")
    public ResponseEntity<Map<String, String>> clearCache() {
        productService.clearAllCaches();
        return ResponseEntity.ok(Map.of("status", "Cache cleared and query counters reset"));
    }

    @PostMapping("/simulation/latency")
    public ResponseEntity<Map<String, Object>> configureLatency(@RequestParam long ms) {
        productService.setDbLatencyMs(ms);
        return ResponseEntity.ok(Map.of("dbLatencyMs", ms));
    }
}
