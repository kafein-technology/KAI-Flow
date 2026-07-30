# MySQL Node'ları — Geliştirici Devir Notu

Bu belge, MySQL Node ve MySQL Tool Node geliştirmesine başka bir bilgisayarda güvenli biçimde devam edebilmek için hazırlanmıştır. Gerçek credential, parola veya kullanıcı verisi içermez.

## 1. İki node neden ayrı?

| Node | Kullanım | Bağlantılar | Güvenlik sınırı |
| --- | --- | --- | --- |
| **MySQL** | Normal workflow adımı olarak CRUD ve parametrik SQL çalıştırır | Sol tarafta normal veri girişi, sağ tarafta `output` | Agent'a tool vermez |
| **MySQL Tool** | Agent'ın ihtiyaç duyduğu anda SQL çalıştırabilmesi için LangChain tool üretir | Yalnızca sağ tarafta `tool` | Yetki profili, tablo allowlist'i ve satır limiti uygular |

Normal MySQL Node'un Agent'a tool çıkışı yoktur. Agent bağlantısı gerektiğinde yalnızca MySQL Tool kullanılmalıdır.

## 2. PR ve branch düzeni

- `codex/mysql-node-ui`: `dev` tabanlıdır; credential, bağlantı sürücüsü, normal MySQL Node, şema keşfi, özel arayüz, demo Docker kurulumu ve normal node testlerini içerir.
- `codex/mysql-tool-node`: ilk branch'in üzerine kuruludur; yalnızca Agent tool sağlayıcısını, güvenlik testlerini ve Agent örnek workflow'larını ekler.

İkinci PR incelenirken önce ilk PR'ın değişiklikleri dikkate alınmalıdır. İlk PR birleştikten sonra ikinci PR'ın base branch'i `dev` olarak değiştirilebilir.

## 3. Dosya haritası

### Ortak altyapı ve normal MySQL Node

- `backend/app/nodes/integrations/mysql_node.py`
  - PyMySQL bağlantısını ve isteğe bağlı SSH tünelini açar/kapatır.
  - Credential'ı node yapılandırmasıyla birleştirir.
  - `Execute Query`, `Select`, `Insert`, `Update`, `Insert or Update` ve `Delete` işlemlerini SQL'e çevirir.
  - Tablo/sütun adlarını quote eder; değerleri SQL parametresi olarak geçirir.
  - MySQL'e özgü `Decimal`, büyük integer, tarih ve byte değerlerini JSON uyumlu hale getirir.
- `backend/app/api/mysql.py`
  - Oturum açmış kullanıcıya ait MySQL credential üzerinden tablo ve sütun listesini okur.
  - Credential sırrını frontend'e göndermez.
- `backend/app/api/credentials.py`
  - MySQL credential testinde `SELECT 1` çalıştırır.
- `backend/main.py`
  - MySQL keşif API router'ını kaydeder.
- `client/app/components/node/mysql/MySQLNodeForm.tsx`
  - PostgreSQL Node arayüzündeki tek sütun kart düzenini uygular.
  - Tablo ve sütunları aranabilir dropdown olarak sunar.
  - Select için çoklu sütun, Return All/Limit, sıralama ve filtre alanlarını gösterir.
  - Görsel alanları backend'in `output_columns`, `sort` ve `where` biçimlerine dönüştürür.
- `client/app/services/mysqlService.ts`
  - Tablo/sütun keşif API çağrılarını yapar.
- `client/app/types/credentials.ts`
  - MySQL credential form alanlarını tanımlar.
- `client/app/components/credentials/DynamicCredentialForm.tsx`
  - `showEmptyOption: false` olan select alanlarında boş seçeneği gizler.
- `client/app/components/canvas/FlowCanvas.tsx`
  - Normal MySQL Node için özel formu seçer.
- `client/public/icons/mysql.svg`
  - Her iki node'un ortak MySQL ikonudur.
- `docker-compose.yml`, `docker/mysql/init/001-demo-schema.sql`
  - Yerel MySQL 8.4 sunucusunu ve demo tablolarını oluşturur.

### MySQL Tool Node

- `backend/app/nodes/integrations/mysql_tool_node.py`
  - Agent'a `BaseTool` verir.
  - Varsayılan `read_only` dahil altı yetki profili sunar.
  - Tek statement zorunluluğu uygular; yorum ve stacked-query kullanımını reddeder.
  - İzinli komutları ve `allowed_tables` listesini sorgu çalışmadan önce denetler.
  - `max_rows` ile SELECT sonuçlarını sınırlar.
- `backend/tests/test_mysql_tool_node.py`
  - Tool shape, yetki profilleri, SQL ayrıştırma ve allowlist reddini test eder.

## 4. Arayüz veri akışı

1. Kullanıcı MySQL credential seçer.
2. Frontend `GET /api/v1/mysql/tables?credential_id=...` çağrısıyla tabloları getirir.
3. Tablo seçilince `GET /api/v1/mysql/columns?...&table=...` çağrısı yapılır.
4. Kullanıcı sütun, sıralama ve filtreyi görsel alanlardan seçer.
5. Form kaydedilirken:
   - sütunlar `output_columns: "id, email"`,
   - sıralama `sort: [{"column":"id","direction":"ASC"}]`,
   - filtre `where: [{"column":"city","condition":"=","value":"Istanbul"}]`
     biçimine çevrilir.
6. Backend değerleri parametrik SQL ile çalıştırır ve JSON uyumlu sonuç döndürür.

Eski workflow'larda doğrudan kaydedilmiş `where`, `sort` ve `output_columns` değerleri form açılırken yeni görsel alanlara geri okunur.

## 5. Güvenlik kararları

- `react_agent.py` değiştirilmez; MySQL Tool standart `BaseTool` çıktısı kullanır.
- Normal MySQL Node'dan Agent tool bağlantısı kurulamaz.
- SQL değerleri string birleştirme ile değil `%s` parametreleriyle gönderilir.
- Dinamik identifier yalnızca doğrulanıp backtick ile quote edilir.
- Keşif API'leri kullanıcı sahipliğini credential servisi üzerinden doğrular.
- MySQL Tool varsayılan olarak salt okunurdur.
- `allowed_tables` kullanılıyorsa tablo kapsamı doğrulanamayan metadata sorguları reddedilir.
- Tool tek SQL statement kabul eder; SQL yorumlarını ve stacked statement'ları reddeder.
- Üretimde ayrıca veritabanında minimum yetkili ayrı bir MySQL kullanıcısı kullanılmalıdır.

## 6. Yerel çalışma

```bash
docker compose up -d mysql
```

Demo credential:

```text
Host: localhost
Port: 3306
Database: kai_demo
User: kai
Password: kai
SSL: kapalı
SSH Tunnel: kapalı
```

Backend bir Docker container içinden çalışıyorsa `Host` alanında `localhost` yerine compose servis adı olan `mysql` kullanılmalıdır.

## 7. Test komutları

Frontend:

```bash
cd client
npm run build
```

Backend unit testleri:

```bash
cd backend
python -m pytest tests/test_mysql_node.py tests/test_mysql_tool_node.py tests/test_mysql_workflow_templates.py -q
```

Yerel MySQL smoke testleri:

```powershell
$env:MYSQL_SMOKE_HOST='127.0.0.1'
$env:MYSQL_SMOKE_PORT='3306'
$env:MYSQL_SMOKE_DATABASE='kai_demo'
$env:MYSQL_SMOKE_USER='kai'
$env:MYSQL_SMOKE_PASSWORD='kai'
python -m pytest tests/test_mysql_node.py tests/test_mysql_workflow_templates.py -q
```

## 8. Örnek workflow'lar

- Normal node için: `client/app/data/templates/mysql-current-crud-test.json`
- Agent tool için: `client/app/data/templates/mysql-current-agent-tool-test.json`
- Ayrıntılı test matrisi: `client/app/data/templates/MYSQL_TEST_WORKFLOWS.md`

Workflow JSON'larındaki credential kimliği ortama özgü olduğu için import sonrasında ilgili node'lardan credential tekrar seçilmelidir.

## 9. Devam ederken kontrol listesi

1. Önce normal MySQL Node PR'ını checkout edin ve build/test sonucunu doğrulayın.
2. Tool geliştirmesi için ikinci branch'e geçin.
3. Metadata veya bağlantı yönü değişirse en yakın `CODEBASE.md` dosyasını güncelleyin.
4. Yeni SQL komutuna izin verilecekse hem `_ACCESS_COMMANDS` hem güvenlik testlerini birlikte güncelleyin.
5. Credential sırlarını test dosyasına veya dokümana koymayın.
6. `react_agent.py` üzerinde değişiklik yapmadan standart provider/tool sözleşmesini koruyun.
