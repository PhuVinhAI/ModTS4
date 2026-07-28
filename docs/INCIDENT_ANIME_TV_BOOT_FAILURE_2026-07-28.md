# Sự cố Anime TV làm The Sims 4 không khởi động (2026-07-28)

## Tóm tắt

Game phiên bản `1.126.73.1030` không vào được khi thư mục mod
`Mods\tomis_ModTS4` tồn tại, nhưng chạy bình thường ngay sau khi xóa mod. Game
executable, EA App, save và thư mục cài đặt không phải nguyên nhân.

Sự cố có hai lỗi trong file `tomis_AnimeTV.package`:

1. Builder sao chép `tv_WatchKids` từ `SimulationFullBuild0.package` và bỏ qua
   bản override mới hơn trong `SimulationDeltaBuild0.package`.
2. STBL được mã hóa bằng Python với trường `mnStringLength` sai định dạng.

Hai lỗi đã được sửa và xác nhận trực tiếp bằng hai lần khởi động game:

- `package-only`: game vào được.
- `package + ts4script`: game vào được và người dùng xác nhận chạy ổn.

## Nguyên nhân 1: lấy tuning cũ từ Full thay vì Delta

EA patch giữ một bản `tv_WatchKids` cũ trong:

```text
Data\Simulation\SimulationFullBuild0.package
```

và ghi đè nó bằng bản mới trong:

```text
Data\Simulation\SimulationDeltaBuild0.package
```

Builder cũ chỉ đọc Full nên tạo custom interaction từ schema cũ. Sau bản cập
nhật ngày 2026-07-25, hai tuning khác nhau đáng kể:

| Dữ liệu | Tuning cũ trong mod | Tuning đã sửa từ Delta |
| --- | ---: | ---: |
| Kích thước XML | 4.851 byte | 8.872 byte |
| Số XML element | 191 | 369 |
| Có `appropriateness_tags` | Không | Có |
| Có `basic_extras` | Không | Có |
| Có `content_score` | Không | Có |
| Có `off_channel` | Không | Có |

DBPF vẫn mở được bằng parser, nhưng điều đó chỉ chứng minh container không hỏng;
nó không chứng minh XML tuning tương thích với schema của game hiện tại.

### Cách sửa

`util/anime_package.py` hiện tìm tuning theo thứ tự:

1. `SimulationDeltaBuild0.package`
2. `SimulationFullBuild0.package` (chỉ dùng làm fallback)

`util/datamining/tuning_splitter.py` có
`find_combined_tuning_by_name()` để resolve đúng một tuning cùng toàn bộ shared
reference mà không sao chép tất cả 47.595 entry của Delta.

## Nguyên nhân 2: header STBL sai

Encoder Python cũ đặt `mnStringLength` bằng tổng số byte UTF-8. Theo định dạng
STBL mà `LlamaLogic.Packages.StringTableModel` và các mod đang chạy sử dụng,
trường này phải là:

```text
tổng số byte UTF-8 + số entry
```

Package lỗi có 2 chuỗi:

```text
header cũ: 62
header đúng: 64
```

Parser Python cũ bỏ qua trường header này nên toàn bộ test cũ vẫn pass. Đây là
lý do không được dùng parser tự viết làm nguồn xác nhận duy nhất.

### Cách sửa

`build_stbl()` không còn tự dùng `struct.pack`. Python gọi lệnh `encode-stbl`
của `tools/Ts4PackageTool`, và lệnh này dùng trực tiếp
`LlamaLogic.Packages.Models.StringTableModel` để encode.

Tool cũng có lệnh `validate` để:

- mở toàn bộ DBPF bằng LlamaLogic;
- decode tất cả STBL bằng `StringTableModel`;
- parse InteractionTuning XML;
- kiểm tra thuộc tính XML `s` khớp instance ID trong DBPF.

## Những phần đã được loại trừ

- `TS4_x64.exe` không bị xóa hoặc làm hỏng: game chạy ngay khi bỏ mod.
- Chuỗi tiếng Việt vẫn là UTF-8 đúng; chữ lỗi trước đó chỉ do PowerShell cũ
  hiển thị sai encoding.
- `.ts4script` dùng đúng magic Python 3.7 của game: `420d0d0a`.
- Cả 7 file `.pyc` trong script đều đọc được bằng Python 3.7.
- Các API script đang import vẫn tồn tại trong game `1.126.73.1030`.
- Không có `lastException`, `lastCrash` hoặc `lastUIException` mới trong hai lần
  test bản sửa.

## Kết quả xác minh bản sửa

```text
dotnet build: 0 warning, 0 error
pytest: 339 passed
LlamaLogic validate: 19 resources, 1 interaction tuning, 18 string tables
DBPF: 2.1
Unresolved <r> reference: 0
Thuộc tính x còn lại: 0
STBL mnStringLength: 64/64
```

Artifact đã chạy được trong game:

```text
tomis_AnimeTV.package
SHA-256 C85B3E7B96325D41A9740AB0EB1AC42918BBD96A82AD41E08EEBE9730B59D169

tomis_ModTS4.ts4script
SHA-256 B710B42DD4CFBCD994CB0A5E937F6FF0F0B26E90436C20D80706B4BAF6B47986
```

## Checklist bắt buộc sau mỗi lần EA cập nhật game

Chạy hoàn toàn bằng Windows PowerShell, không dùng WSL hoặc Docker:

```powershell
.\.venv\Scripts\python.exe build_anime_package.py
dotnet tools\Ts4PackageTool\bin\Release\net8.0\Ts4PackageTool.dll validate assets\tomis_AnimeTV.package
.\.venv\Scripts\python.exe -m pytest -q
```

Sau đó kiểm tra theo thứ tự:

1. Xác nhận version game và ngày sửa của cả Full/Delta.
2. Build lại package từ game vừa cập nhật, không tái sử dụng package cũ.
3. Chạy validator LlamaLogic và toàn bộ test.
4. Test game với `package-only` trước.
5. Chỉ khi game vào được mới thêm `.ts4script` và test bản đầy đủ.
6. Kiểm tra timestamp của `lastException`, `lastCrash` và `lastUIException`;
   không quy lỗi cho report cũ.

Các bản cô lập được tạo tại:

```text
build\recovery\package-only
build\recovery\script-only
build\recovery\full
```

Nếu game lại không khởi động, chỉ gỡ:

```text
Documents\Electronic Arts\The Sims 4\Mods\tomis_ModTS4
```

Không xóa game executable, save, Tray hoặc cài lại game trước khi thử cô lập
mod theo quy trình trên.
