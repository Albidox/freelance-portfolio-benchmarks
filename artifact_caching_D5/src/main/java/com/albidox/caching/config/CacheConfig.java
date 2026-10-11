package com.albidox.caching.config;

import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.jsontype.BasicPolymorphicTypeValidator;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.github.benmanes.caffeine.cache.Caffeine;
import java.io.IOException;
import java.time.Duration;
import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.support.SimpleValueWrapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableCaching
public class CacheConfig {

    public static final String CACHE_PRODUCTS = "products";
    public static final String CACHE_NEGATIVE = "negative_products";

    @Value("${app.caching.ttl-seconds:600}")
    private long ttlSeconds;

    @Value("${app.caching.null-caching-allowed:false}")
    private boolean nullCachingAllowed;

    @Bean
    public ObjectMapper cachingObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        mapper.disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
        return mapper;
    }

    @Bean
    public JacksonSerializedCacheManager cacheManager(ObjectMapper cachingObjectMapper) {
        return new JacksonSerializedCacheManager(cachingObjectMapper, ttlSeconds, nullCachingAllowed);
    }

    public static class JacksonSerializedCacheManager implements CacheManager {

        private final ObjectMapper objectMapper;
        private final long ttlSeconds;
        private final boolean nullCachingAllowed;
        private final ConcurrentHashMap<String, JacksonSerializedCache> caches = new ConcurrentHashMap<>();

        public JacksonSerializedCacheManager(ObjectMapper objectMapper, long ttlSeconds, boolean nullCachingAllowed) {
            this.objectMapper = objectMapper;
            this.ttlSeconds = ttlSeconds;
            this.nullCachingAllowed = nullCachingAllowed;
        }

        @Override
        public Cache getCache(String name) {
            return caches.computeIfAbsent(name, n -> {
                if (CACHE_NEGATIVE.equals(n)) {
                    return new JacksonSerializedCache(n, objectMapper, 60L, true);
                }
                return new JacksonSerializedCache(n, objectMapper, ttlSeconds, nullCachingAllowed);
            });
        }

        @Override
        public Collection<String> getCacheNames() {
            return Collections.unmodifiableSet(caches.keySet());
        }

        public JacksonSerializedCache getCustomCache(String name) {
            return (JacksonSerializedCache) getCache(name);
        }
    }

    public static class CachePayload {
        private final Class<?> targetClass;
        private final byte[] payload;

        public CachePayload(Class<?> targetClass, byte[] payload) {
            this.targetClass = targetClass;
            this.payload = payload;
        }

        public Class<?> getTargetClass() {
            return targetClass;
        }

        public byte[] getPayload() {
            return payload;
        }
    }

    public static class JacksonSerializedCache implements Cache {

        private final String name;
        private final ObjectMapper objectMapper;
        private final long ttlSeconds;
        private final boolean nullCachingAllowed;

        private final com.github.benmanes.caffeine.cache.Cache<Object, CachePayload> nativeCache;

        private final AtomicLong hitCount = new AtomicLong(0);
        private final AtomicLong missCount = new AtomicLong(0);
        private final AtomicLong putCount = new AtomicLong(0);
        private final AtomicLong evictCount = new AtomicLong(0);

        public JacksonSerializedCache(String name, ObjectMapper objectMapper, long ttlSeconds, boolean nullCachingAllowed) {
            this.name = name;
            this.objectMapper = objectMapper;
            this.ttlSeconds = ttlSeconds;
            this.nullCachingAllowed = nullCachingAllowed;
            this.nativeCache = Caffeine.newBuilder()
                    .expireAfterWrite(Duration.ofSeconds(ttlSeconds))
                    .maximumSize(50_000)
                    .recordStats()
                    .build();
        }

        @Override
        public String getName() {
            return name;
        }

        @Override
        public Object getNativeCache() {
            return nativeCache;
        }

        @Override
        public ValueWrapper get(Object key) {
            if (key == null) {
                return null;
            }
            CachePayload entry = nativeCache.getIfPresent(key);
            if (entry == null) {
                missCount.incrementAndGet();
                return null;
            }
            hitCount.incrementAndGet();
            try {
                Object value = objectMapper.readValue(entry.getPayload(), entry.getTargetClass());
                return new SimpleValueWrapper(value);
            } catch (IOException e) {
                throw new IllegalStateException("Failed to deserialize cached JSON payload for key: " + key, e);
            }
        }

        @Override
        @SuppressWarnings("unchecked")
        public <T> T get(Object key, Class<T> type) {
            if (key == null) {
                return null;
            }
            CachePayload entry = nativeCache.getIfPresent(key);
            if (entry == null) {
                missCount.incrementAndGet();
                return null;
            }
            hitCount.incrementAndGet();
            try {
                Class<T> target = type != null ? type : (Class<T>) entry.getTargetClass();
                return objectMapper.readValue(entry.getPayload(), target);
            } catch (IOException e) {
                throw new IllegalStateException("Failed to deserialize cached JSON payload to " + (type != null ? type.getName() : "unknown") + " for key: " + key, e);
            }
        }

        @Override
        public <T> T get(Object key, Callable<T> valueLoader) {
            if (key == null) {
                return null;
            }
            CachePayload existing = nativeCache.getIfPresent(key);
            if (existing != null) {
                hitCount.incrementAndGet();
                try {
                    @SuppressWarnings("unchecked")
                    T value = (T) objectMapper.readValue(existing.getPayload(), existing.getTargetClass());
                    return value;
                } catch (IOException e) {
                    throw new IllegalStateException("Failed to deserialize cached JSON payload for key: " + key, e);
                }
            }

            missCount.incrementAndGet();
            synchronized (this) {
                existing = nativeCache.getIfPresent(key);
                if (existing != null) {
                    try {
                        @SuppressWarnings("unchecked")
                        T value = (T) objectMapper.readValue(existing.getPayload(), existing.getTargetClass());
                        return value;
                    } catch (IOException e) {
                        throw new IllegalStateException("Failed to deserialize cached JSON payload for key: " + key, e);
                    }
                }
                try {
                    T loaded = valueLoader.call();
                    put(key, loaded);
                    return loaded;
                } catch (Exception e) {
                    throw new ValueRetrievalException(key, valueLoader, e);
                }
            }
        }

        @Override
        public void put(Object key, Object value) {
            if (key == null) {
                return;
            }
            if (value == null) {
                if (!nullCachingAllowed) {
                    // Null caching disabled by configuration
                    return;
                }
            }
            try {
                byte[] bytes = objectMapper.writeValueAsBytes(value);
                Class<?> clazz = value != null ? value.getClass() : Object.class;
                nativeCache.put(key, new CachePayload(clazz, bytes));
                putCount.incrementAndGet();
            } catch (Exception e) {
                throw new IllegalStateException("Failed to serialize cache value for key: " + key, e);
            }
        }

        @Override
        public ValueWrapper putIfAbsent(Object key, Object value) {
            if (key == null) {
                return null;
            }
            CachePayload existing = nativeCache.getIfPresent(key);
            if (existing != null) {
                try {
                    return new SimpleValueWrapper(objectMapper.readValue(existing.getPayload(), existing.getTargetClass()));
                } catch (IOException e) {
                    throw new IllegalStateException("Failed to deserialize cached JSON payload for key: " + key, e);
                }
            }
            put(key, value);
            return null;
        }

        @Override
        public void evict(Object key) {
            if (key != null) {
                nativeCache.invalidate(key);
                evictCount.incrementAndGet();
            }
        }

        public boolean containsKey(Object key) {
            return key != null && nativeCache.getIfPresent(key) != null;
        }

        @Override
        public void clear() {
            nativeCache.invalidateAll();
        }

        public Map<String, Object> getMetrics() {
            long hits = hitCount.get();
            long misses = missCount.get();
            long total = hits + misses;
            double hitRatio = total > 0 ? ((double) hits / total) * 100.0 : 0.0;

            return Map.of(
                    "cacheName", name,
                    "ttlSeconds", ttlSeconds,
                    "nullCachingAllowed", nullCachingAllowed,
                    "hitCount", hits,
                    "missCount", misses,
                    "totalRequests", total,
                    "hitRatioPercent", Math.round(hitRatio * 100.0) / 100.0,
                    "putCount", putCount.get(),
                    "evictCount", evictCount.get(),
                    "size", nativeCache.estimatedSize()
            );
        }
    }
}
