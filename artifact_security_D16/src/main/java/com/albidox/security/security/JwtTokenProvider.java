package com.albidox.security.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.MalformedJwtException;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.UnsupportedJwtException;
import io.jsonwebtoken.security.Keys;
import io.jsonwebtoken.security.SignatureException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.util.Base64;
import java.util.Collection;
import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

@Component
public class JwtTokenProvider {

    private static final Logger log = LoggerFactory.getLogger(JwtTokenProvider.class);

    private final Key signingKey;
    private final long tokenValidityInMilliseconds;

    public JwtTokenProvider(
            @Value("${jwt.secret}") String secret,
            @Value("${jwt.expiration:3600000}") long tokenValidityInMilliseconds) {
        this.signingKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.tokenValidityInMilliseconds = tokenValidityInMilliseconds;
    }

    public String generateToken(String username, List<String> roles) {
        Date now = new Date();
        Date validity = new Date(now.getTime() + this.tokenValidityInMilliseconds);

        return Jwts.builder()
                .setSubject(username)
                .claim("roles", roles)
                .setIssuedAt(now)
                .setExpiration(validity)
                .signWith(this.signingKey, SignatureAlgorithm.HS256)
                .compact();
    }

    public String generateExpiredToken(String username, List<String> roles) {
        Date now = new Date();
        Date expiredAt = new Date(now.getTime() - 10000);

        return Jwts.builder()
                .setSubject(username)
                .claim("roles", roles)
                .setIssuedAt(new Date(now.getTime() - 20000))
                .setExpiration(expiredAt)
                .signWith(this.signingKey, SignatureAlgorithm.HS256)
                .compact();
    }

    public String generateNoneAlgorithmToken(String username, List<String> roles) {
        String headerJson = "{\"alg\":\"none\",\"typ\":\"JWT\"}";
        String headerBase64 = Base64.getUrlEncoder().withoutPadding().encodeToString(headerJson.getBytes(StandardCharsets.UTF_8));
        String rolesFormatted = roles.stream().map(r -> "\"" + r + "\"").collect(Collectors.joining(","));
        long nowSec = System.currentTimeMillis() / 1000;
        String payloadJson = "{\"sub\":\"" + username + "\",\"roles\":[" + rolesFormatted + "],\"iat\":" + nowSec + ",\"exp\":" + (nowSec + 3600) + "}";
        String payloadBase64 = Base64.getUrlEncoder().withoutPadding().encodeToString(payloadJson.getBytes(StandardCharsets.UTF_8));
        return headerBase64 + "." + payloadBase64 + ".";
    }

    public String generateUnsignedToken(String username, List<String> roles) {
        String headerJson = "{\"typ\":\"JWT\"}";
        String headerBase64 = Base64.getUrlEncoder().withoutPadding().encodeToString(headerJson.getBytes(StandardCharsets.UTF_8));
        String rolesFormatted = roles.stream().map(r -> "\"" + r + "\"").collect(Collectors.joining(","));
        long nowSec = System.currentTimeMillis() / 1000;
        String payloadJson = "{\"sub\":\"" + username + "\",\"roles\":[" + rolesFormatted + "],\"iat\":" + nowSec + ",\"exp\":" + (nowSec + 3600) + "}";
        String payloadBase64 = Base64.getUrlEncoder().withoutPadding().encodeToString(payloadJson.getBytes(StandardCharsets.UTF_8));
        return headerBase64 + "." + payloadBase64 + ".";
    }

    public TokenValidationStatus validateTokenWithStatus(String token) {
        if (token == null || token.isBlank()) {
            return TokenValidationStatus.EMPTY;
        }

        // Defense in depth: Inspect token header for algorithm confusion ('alg': 'none')
        try {
            String[] parts = token.split("\\.");
            if (parts.length >= 2) {
                byte[] decodedHeader = Base64.getUrlDecoder().decode(parts[0]);
                String headerJson = new String(decodedHeader, StandardCharsets.UTF_8).toLowerCase();
                if (headerJson.contains("\"alg\":\"none\"") || headerJson.contains("\"alg\": \"none\"")
                        || headerJson.contains("\"alg\" : \"none\"") || headerJson.contains("\"alg\" :\"none\"")) {
                    log.warn("SECURITY ALERT: Algorithm confusion attack detected ('alg': 'none'). Rejecting forged token without accepting claims.");
                    return TokenValidationStatus.ALGORITHM_CONFUSION;
                }
            }
        } catch (Exception ex) {
            log.warn("Failed to inspect JWT header during pre-validation: {}", ex.getMessage());
        }

        try {
            Jwts.parserBuilder()
                    .setSigningKey(this.signingKey)
                    .build()
                    .parseClaimsJws(token);
            return TokenValidationStatus.VALID;
        } catch (ExpiredJwtException ex) {
            log.warn("JWT token expired: {}", ex.getMessage());
            return TokenValidationStatus.EXPIRED;
        } catch (UnsupportedJwtException ex) {
            log.warn("Unsupported JWT token: {}", ex.getMessage());
            return TokenValidationStatus.UNSUPPORTED;
        } catch (MalformedJwtException ex) {
            log.warn("Malformed JWT token: {}", ex.getMessage());
            return TokenValidationStatus.MALFORMED;
        } catch (SignatureException ex) {
            log.warn("Invalid JWT signature: {}", ex.getMessage());
            return TokenValidationStatus.INVALID_SIGNATURE;
        } catch (IllegalArgumentException ex) {
            log.warn("JWT claims string is empty or illegal: {}", ex.getMessage());
            return TokenValidationStatus.EMPTY;
        } catch (JwtException ex) {
            log.warn("JWT token validation failed: {}", ex.getMessage());
            return TokenValidationStatus.MALFORMED;
        }
    }

    public boolean validateToken(String token) {
        return validateTokenWithStatus(token) == TokenValidationStatus.VALID;
    }

    public String getUsernameFromToken(String token) {
        Claims claims = parseClaims(token);
        return claims.getSubject();
    }

    @SuppressWarnings("unchecked")
    public List<String> getRolesFromToken(String token) {
        Claims claims = parseClaims(token);
        Object rolesObj = claims.get("roles");
        if (rolesObj instanceof List<?> list) {
            return list.stream()
                    .map(Object::toString)
                    .collect(Collectors.toList());
        }
        return List.of();
    }

    public Collection<? extends GrantedAuthority> getAuthoritiesFromToken(String token) {
        List<String> roles = getRolesFromToken(token);
        return roles.stream()
                .map(role -> {
                    String authority = role.startsWith("ROLE_") ? role : "ROLE_" + role;
                    return new SimpleGrantedAuthority(authority);
                })
                .collect(Collectors.toList());
    }

    private Claims parseClaims(String token) {
        return Jwts.parserBuilder()
                .setSigningKey(this.signingKey)
                .build()
                .parseClaimsJws(token)
                .getBody();
    }
}
