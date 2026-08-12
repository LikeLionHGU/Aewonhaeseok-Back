package com.awon.backend.mapping;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface MappingRunRepository extends JpaRepository<MappingRun, Long> {

    /** 가장 최근 회차. 목록 화면처럼 집계값만 필요할 때 쓴다. */
    Optional<MappingRun> findFirstByFileIdOrderByRoundNoDesc(Long fileId);

    /**
     * 가장 최근 회차를 컬럼까지 한 번에 가져온다.
     *
     * <p>컬럼은 지연 로딩이라 트랜잭션이 끝난 뒤 컨트롤러에서 건드리면
     * LazyInitializationException이 난다. 결과 응답을 만들 때는 반드시 이쪽을 쓴다.
     */
    @Query("""
            select r from MappingRun r
            left join fetch r.columns
            where r.fileId = :fileId
              and r.roundNo = (select max(x.roundNo) from MappingRun x where x.fileId = :fileId)
            """)
    Optional<MappingRun> findLatestWithColumns(Long fileId);

    /** 전후 비교용. 1차부터 순서대로. */
    List<MappingRun> findByFileIdOrderByRoundNoAsc(Long fileId);

    @Query("select coalesce(max(r.roundNo), 0) from MappingRun r where r.fileId = :fileId")
    int findMaxRoundNo(Long fileId);
}
