package com.awon.backend.openapi;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import jakarta.persistence.LockModeType;
import java.util.Optional;
public interface OrganizationRepository extends JpaRepository<Organization,Long> {
    boolean existsByName(String name);
    Optional<Organization> findByOwnerUserId(Long ownerUserId);
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select o from Organization o where o.ownerUserId = :ownerUserId")
    Optional<Organization> findOwnedForUpdate(@Param("ownerUserId") Long ownerUserId);
}
