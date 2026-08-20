package com.awon.backend.review;

import com.awon.backend.auth.CurrentUser;
import com.awon.backend.dictionary.TermNameCache;
import com.awon.backend.mapping.MappingColumn;
import com.awon.backend.mapping.MappingStatus;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ReviewServiceTest {

    @Test
    void rejectedAliasesAreStoredAsCanonicalNoMatch() {
        ReviewItemRepository repository = mock(ReviewItemRepository.class);
        TermNameCache terms = mock(TermNameCache.class);
        CurrentUser currentUser = mock(CurrentUser.class);
        MappingColumn column = new MappingColumn(
                2, "시료구분", "시료구분", MappingStatus.unmapped,
                null, null, null, null, null, null, BigDecimal.ZERO, null);
        ReviewItem item = new ReviewItem(column, 1L, Map.of());
        when(currentUser.id()).thenReturn(7L);
        when(currentUser.reviewerName("tester")).thenReturn("tester");
        when(repository.findOwnedById(7L, 10L)).thenReturn(Optional.of(item));

        ReviewController.ReviewService service =
                new ReviewController.ReviewService(repository, terms, currentUser);
        ReviewItem decided = service.decide(10L, "rejected", null, "tester");

        assertEquals("no_match", decided.getVerdict());
        assertEquals(null, decided.adoptedCode());
    }
}
