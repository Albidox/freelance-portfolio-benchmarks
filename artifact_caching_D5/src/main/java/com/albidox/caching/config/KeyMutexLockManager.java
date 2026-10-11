package com.albidox.caching.config;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;
import org.springframework.stereotype.Component;

/**
 * Key-level distributed and reentrant mutex lock coordinator.
 * Prevents Cache Stampede / Thundering Herd by guaranteeing that only
 * one thread queries the persistent database upon cache miss or key expiration.
 */
@Component
public class KeyMutexLockManager {

    private final ConcurrentHashMap<String, ReentrantLock> locks = new ConcurrentHashMap<>();

    public ReentrantLock getLock(String key) {
        return locks.computeIfAbsent(key, k -> new ReentrantLock());
    }

    public void acquire(String key) {
        ReentrantLock lock = getLock(key);
        lock.lock();
    }

    public boolean tryAcquire(String key, long timeoutMs) throws InterruptedException {
        ReentrantLock lock = getLock(key);
        return lock.tryLock(timeoutMs, TimeUnit.MILLISECONDS);
    }

    public void release(String key) {
        ReentrantLock lock = locks.get(key);
        if (lock != null && lock.isHeldByCurrentThread()) {
            lock.unlock();
            if (!lock.isLocked() && !lock.hasQueuedThreads()) {
                locks.remove(key, lock);
            }
        }
    }

    public int activeLockCount() {
        return locks.size();
    }

    public void clear() {
        locks.clear();
    }
}
