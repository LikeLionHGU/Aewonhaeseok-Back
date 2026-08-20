package com.awon.backend.file;

import com.awon.backend.auth.CurrentUser;
import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.mapping.MappingRunRepository;
import com.awon.backend.review.ReviewItemRepository;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class FileServiceOwnershipTest {
    @Test
    void foreignFileIdLooksNotFound() {
        UploadedFileRepository repository = mock(UploadedFileRepository.class);
        CurrentUser currentUser = mock(CurrentUser.class);
        when(currentUser.id()).thenReturn(22L);
        when(repository.findByIdAndOwnerUserId(10L, 22L)).thenReturn(Optional.empty());
        FileService service = new FileService(repository, mock(MappingRunRepository.class),
                mock(ReviewItemRepository.class), mock(FileStorage.class),
                mock(JdbcTemplate.class), currentUser);

        ApiException error = assertThrows(ApiException.class, () -> service.get(10L));
        assertEquals(ErrorCode.FILE_NOT_FOUND, error.errorCode());
        verify(repository).findByIdAndOwnerUserId(10L, 22L);
    }
}
