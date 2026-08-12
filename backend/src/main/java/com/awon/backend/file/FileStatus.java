package com.awon.backend.file;

/**
 * 파일 처리 단계. API 명세서 B2의 status와 같다.
 *
 * <p>uploaded → mapping → mapped → reviewing → completed
 */
public enum FileStatus {
    /** 접수됨. 아직 매핑 전 */
    uploaded,
    /** 매핑 진행 중 */
    mapping,
    /** 매핑 끝. 확인할 컬럼이 없으면 여기서 completed로 간다 */
    mapped,
    /** 사람이 판정해야 할 컬럼이 남아 있음 */
    reviewing,
    /** 모든 컬럼이 확정됨 */
    completed,
    /** 매핑 실패 */
    failed
}
