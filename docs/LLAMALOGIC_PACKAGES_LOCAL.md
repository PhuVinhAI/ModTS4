# LlamaLogic.Packages — tài liệu và source local

Workspace đã ghim source upstream tại:

```text
vendor/LlamaLogic/
```

Đây là git submodule shallow của `https://github.com/Llama-Logic/LlamaLogic`,
đang trỏ tới revision của dòng `LlamaLogic.Packages 3.8.2`. Source, unit test,
XML/YAML API docs và HTML docs đều có sẵn offline trong submodule.

## Điểm tra cứu chính

| Mục đích | File local |
|---|---|
| Container DBPF đọc/ghi | `vendor/LlamaLogic/LlamaLogic.Packages/DataBasePackedFile.cs` |
| TGI key | `vendor/LlamaLogic/LlamaLogic.Packages/ResourceKey.cs` |
| Resource type enum | `vendor/LlamaLogic/LlamaLogic.Packages/ResourceType.cs` |
| Chế độ nén | `vendor/LlamaLogic/LlamaLogic.Packages/CompressionMode.cs` |
| Thứ tự index | `vendor/LlamaLogic/LlamaLogic.Packages/ResourceKeyOrder.cs` |
| STBL model | `vendor/LlamaLogic/LlamaLogic.Packages/Models/StringTableModel.cs` |
| PNG → DST/DDS | `vendor/LlamaLogic/LlamaLogic.Packages/Formats/DirectDrawSurface.cs` |
| Unit test DBPF | `vendor/LlamaLogic/LlamaLogic.Packages.UnitTests/DataBasePackedFileTests.cs` |
| API HTML `DataBasePackedFile` | `vendor/LlamaLogic/docs/packages/LlamaLogic.Packages.DataBasePackedFile.html` |
| API HTML `ResourceKey` | `vendor/LlamaLogic/docs/packages/LlamaLogic.Packages.ResourceKey.html` |
| API HTML `StringTableModel` | `vendor/LlamaLogic/docs/packages/LlamaLogic.Packages.Models.StringTableModel.html` |
| API YAML đầy đủ | `vendor/LlamaLogic/Documentation/packages/` |
| Hướng dẫn NuGet upstream | `vendor/LlamaLogic/LlamaLogic.Packages/README.md` |

Mở HTML offline bằng trình duyệt:

```powershell
Start-Process (Resolve-Path .\vendor\LlamaLogic\docs\packages\LlamaLogic.Packages.DataBasePackedFile.html)
```

## API dùng trong workspace

`tools/Ts4PackageTool/Program.cs` là ví dụ thực tế đang chạy trên Windows.
Python gọi nó qua `util/datamining/package_writer.py`; không tự serialize DBPF.

### Tạo package tuning/STBL

```csharp
using LlamaLogic.Packages;

using var package = new DataBasePackedFile
{
    CreationTime = DateTimeOffset.UnixEpoch,
    UpdatedTime = DateTimeOffset.UnixEpoch
};

var tuningKey = new ResourceKey(
    (ResourceType)0xE882D22F,
    0x00000000,
    0x0123456789ABCDEF);
package.SetXml(tuningKey, tuningXml, CompressionMode.ForceOff);

var stblKey = new ResourceKey(
    ResourceType.StringTable,
    0x80000000,
    0x0011223344556677);
package.Set(stblKey, stringTableModel, CompressionMode.ForceOff);
package.SaveAs(outputPath, ResourceKeyOrder.TypeGroupInstance);
```

`ResourceKey` cũng nhận chuỗi TGI dạng
`type:group:instance`, trong đó `instance` luôn đủ 16 chữ số hex, ví dụ:
`220557da:80000000:0011223344556677`.

### Đọc và extract

```csharp
using var package = new DataBasePackedFile(inputPath);
foreach (var key in package.GetKeys(ResourceKeyOrder.TypeGroupInstance))
{
    var bytes = package.Get(key);       // tự giải nén resource
    var raw = package.GetRaw(key);      // giữ dữ liệu nén nguyên trạng
}

var xml = package.GetXml(tuningKey);
var stbl = package.GetStringTable(stblKey);
var png = package.GetDdsAsPng(imageKey);
```

### STBL và ảnh 2D

- `StringTableModel.Decode(bytes)` đọc STBL hiện có.
- `StringTableModel.Set(hash, text)` sửa một key; `AddNew(text)` tự FNV-32
  hash; `Encode()` tạo lại payload STBL.
- `DataBasePackedFile.SetPngAsDds(key, pngBytes)` chuyển PNG thành DST/DDS
  resource TS4.
- `DataBasePackedFile.SetPngAsTranslucentJpeg(key, pngBytes)` dùng cho resource
  translucent JPEG của TS4.
- `GetDdsAsPng` và `GetTranslucentJpegAsPng` thực hiện chiều ngược lại.

### Compression

`CompressionMode.Auto` chỉ nên dùng khi type có quy tắc nén đã biết. Với custom
type raw của mod, CLI hiện tại dùng `CompressionMode.ForceOff` để giữ hành vi
ổn định và tránh đoán sai catalog nén; API ảnh có chế độ riêng của LlamaLogic.

## Cập nhật submodule

Lần clone workspace mới:

```powershell
git submodule update --init --depth 1 vendor/LlamaLogic
```

Kiểm tra revision đang dùng:

```powershell
git -C vendor/LlamaLogic log -1 --oneline
git submodule status vendor/LlamaLogic
```

Khi muốn nâng LlamaLogic, cập nhật submodule có chủ đích, kiểm tra release
notes/API rồi sửa `PackageReference` và `packages.lock.json` tương ứng:

```powershell
git -C vendor/LlamaLogic fetch --tags
git -C vendor/LlamaLogic checkout <revision-da-review>
git add vendor/LlamaLogic tools/Ts4PackageTool/Ts4PackageTool.csproj tools/Ts4PackageTool/packages.lock.json
```

Source upstream mang MIT License; xem
`vendor/LlamaLogic/LICENSE`. Không sửa trực tiếp file trong submodule để tránh
mất thay đổi khi cập nhật revision.
