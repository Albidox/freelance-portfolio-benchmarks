package com.albidox.security.security;

public enum TokenValidationStatus {
    VALID,
    EXPIRED,
    ALGORITHM_CONFUSION,
    INVALID_SIGNATURE,
    MALFORMED,
    UNSUPPORTED,
    EMPTY
}
