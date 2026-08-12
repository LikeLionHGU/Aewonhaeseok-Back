package com.awon.backend.mapping;

/**
 * 컬럼 판정 결과 4종. 매핑 엔진의 status와 같다.
 *
 * <p>주의: exact는 점수가 없다(null). 사전에 정확히 있었다는 뜻이지
 * 유사도 100점이 아니다. 화면에 "100점"으로 표시하면 안 된다.
 */
public enum MappingStatus {

    /** 사전에 그대로 있음. 점수 없음 */
    exact(true),
    /** 유사도 85점 이상 */
    fuzzy_auto(true),
    /** 70~85점. 사람이 판정해야 한다 */
    needs_review(false),
    /** 70점 미만. 억지로 붙이지 않고 사람에게 넘긴다 */
    unmapped(false);

    private final boolean auto;

    MappingStatus(boolean auto) {
        this.auto = auto;
    }

    /** 자동 확정된 판정인가. 매핑률 집계의 분자가 된다. */
    public boolean isAuto() {
        return auto;
    }

    /** 검증 화면에 띄워야 하는가. */
    public boolean needsHuman() {
        return !auto;
    }
}
