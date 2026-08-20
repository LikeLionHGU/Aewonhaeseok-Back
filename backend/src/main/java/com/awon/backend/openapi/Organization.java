package com.awon.backend.openapi;

import jakarta.persistence.*;
import java.time.OffsetDateTime;

@Entity @Table(name = "organizations")
public class Organization {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @Column(nullable = false, unique = true, length = 200) private String name;
    @Column(nullable = false) private boolean active;
    @Column(name = "created_by_user_id", nullable = false) private Long createdByUserId;
    @Column(name = "owner_user_id", unique = true) private Long ownerUserId;
    @Column(name = "created_at", nullable = false) private OffsetDateTime createdAt;
    protected Organization() { }
    public Organization(String name, long createdByUserId) {
        this.name = name.trim(); this.createdByUserId = createdByUserId;
        this.active = true; this.createdAt = OffsetDateTime.now();
    }
    public static Organization ownedBy(String name, long userId) {
        Organization organization = new Organization(name, userId);
        organization.ownerUserId = userId;
        return organization;
    }
    public Long getId() { return id; }
    public String getName() { return name; }
    public boolean isActive() { return active; }
    public Long getCreatedByUserId() { return createdByUserId; }
    public Long getOwnerUserId() { return ownerUserId; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
}
