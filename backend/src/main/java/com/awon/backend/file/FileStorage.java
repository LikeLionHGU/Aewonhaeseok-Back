package com.awon.backend.file;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.config.AwonProperties;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 업로드 원본을 디스크에 보관한다.
 *
 * <p>원본 파일명을 그대로 경로에 쓰지 않는다. 한글·공백·경로 문자가 섞여 있고
 * 같은 이름이 반복해서 올라오기 때문이다. 대신 UUID로 저장하고 원본 이름은 DB에 남긴다.
 */
@Component
public class FileStorage {

    /** 매핑 엔진이 읽을 수 있는 형식. 엔진의 _DATA_SUFFIXES와 같다. */
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("csv", "xlsx", "xlsm", "xls");

    private static final DateTimeFormatter DATE_DIR = DateTimeFormatter.ofPattern("yyyy/MM/dd");

    private final Path root;

    public FileStorage(AwonProperties props) {
        this.root = Paths.get(props.storage().root()).toAbsolutePath().normalize();
    }

    public record Stored(Path path, String sha256, long sizeBytes) {
    }

    /**
     * 파일을 저장하면서 동시에 SHA-256을 계산한다.
     * 두 번 읽지 않기 위해 스트림에 다이제스트를 물린다.
     */
    public Stored store(MultipartFile file) {
        if (file.isEmpty()) {
            throw new ApiException(ErrorCode.FILE_EMPTY);
        }
        String extension = extensionOf(file.getOriginalFilename());
        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            throw new ApiException(ErrorCode.FILE_FORMAT_UNSUPPORTED,
                    Map.of("given", extension, "allowed", ALLOWED_EXTENSIONS));
        }

        Path directory = root.resolve(LocalDate.now().format(DATE_DIR));
        Path target = directory.resolve(UUID.randomUUID() + "." + extension);

        try {
            Files.createDirectories(directory);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream in = file.getInputStream();
                 DigestInputStream digesting = new DigestInputStream(in, digest)) {
                Files.copy(digesting, target, StandardCopyOption.REPLACE_EXISTING);
            }
            String hash = HexFormat.of().formatHex(digest.digest());
            return new Stored(target, hash, Files.size(target));
        } catch (IOException | NoSuchAlgorithmException e) {
            throw new ApiException(ErrorCode.FILE_STORAGE_FAILED,
                    Map.of("filename", String.valueOf(file.getOriginalFilename())), e);
        }
    }

    /** 원본 파일명에서 소문자 확장자만 뽑는다. 확장자가 없으면 빈 문자열. */
    private String extensionOf(String filename) {
        if (filename == null) {
            return "";
        }
        int dot = filename.lastIndexOf('.');
        if (dot < 0 || dot == filename.length() - 1) {
            return "";
        }
        return filename.substring(dot + 1).toLowerCase(Locale.ROOT);
    }
}
