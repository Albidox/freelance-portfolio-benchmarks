package com.ashfaq.n1.tracker;

import org.hibernate.resource.jdbc.spi.StatementInspector;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

@Component
public class SqlStatementCountTracker implements StatementInspector {

    private static final AtomicInteger QUERY_COUNT = new AtomicInteger(0);
    private static final List<String> QUERIES = new CopyOnWriteArrayList<>();
    private static volatile boolean active = false;

    public SqlStatementCountTracker() {
    }

    @Override
    public String inspect(String sql) {
        if (active && sql != null && !sql.trim().isEmpty()) {
            QUERY_COUNT.incrementAndGet();
            QUERIES.add(sql.trim());
        }
        return sql;
    }

    public void start() {
        active = true;
    }

    public void stop() {
        active = false;
    }

    public void reset() {
        QUERY_COUNT.set(0);
        QUERIES.clear();
        active = true;
    }

    public int getQueryCount() {
        return QUERY_COUNT.get();
    }

    public List<String> getQueries() {
        return Collections.unmodifiableList(new ArrayList<>(QUERIES));
    }

    public String generateFormattedLog() {
        StringBuilder sb = new StringBuilder();
        int index = 1;
        for (String q : QUERIES) {
            sb.append("[HIBERNATE-SQL-").append(index++).append("] ").append(q).append("\n");
        }
        sb.append("TOTAL QUERIES CAPTURED: ").append(QUERY_COUNT.get()).append("\n");
        return sb.toString();
    }
}
