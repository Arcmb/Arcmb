"""Armazém compartilhado dos resultados de simulado, para os painéis da gestão.

Antes, cada clique num filtro do painel da gestão, da análise por turma ou dos relatórios
da escola relia do banco todos os resultados de todos os alunos (dezenas de MB de JSON) e
transformava cada resposta de cada questão num dicionário Python. Com dois ou três pedidos
ao mesmo tempo, isso passava do limite de memória do servidor.

Agora os resultados são lidos uma vez, em lotes pequenos, e guardados de forma compacta:
3 bytes por questão em vez de um dicionário. Os filtros trabalham em cima desta cópia.
A cópia só é refeita quando os dados mudam (uma importação, uma troca de turma etc.) ou,
por segurança, a cada TTL segundos.

Quem usa os registros deve tratá-los como somente leitura: eles são compartilhados entre
os pedidos.
"""
import json
import threading
import time

TTL = 600          # refaz a cópia ao menos a cada 10 minutos, mesmo sem mudança detectada
PAGE = 200         # resultados lidos do banco por vez
AREAS = ('ALL', 'LC', 'CH', 'CN', 'MT')

# Formato compacto: 3 bytes por questão — acertos, total e resposta.
# Acertos e total: 0..250, ou 255 para null.
# Resposta: 0 = sem campo "response", 1 = texto vazio, 32..126 = a própria letra (ASCII).
_NO_RESPONSE = 0
_EMPTY_RESPONSE = 1
_ALLOWED_FIELDS = frozenset(('name', 'correct', 'total', 'response'))


def _json(value):
    if isinstance(value, dict):
        return value
    try:
        loaded = json.loads(value or '{}')
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _get(row, key):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


_NULL = 255        # "correct"/"total" gravados como null (questão anulada ou em branco)


def _small_int(value):
    return value is None or (type(value) is int and 0 <= value <= 250)


def _pack_int(value):
    return _NULL if value is None else value


def _unpack_int(byte):
    return None if byte == _NULL else byte


def _compact(metrics):
    """Devolve (chaves, bytes) ou None se algum item fugir do formato simples."""
    keys = []
    data = bytearray()
    for key, value in metrics.items():
        if not isinstance(key, str) or not isinstance(value, dict) or not set(value) <= _ALLOWED_FIELDS:
            return None
        if 'correct' not in value or 'total' not in value:
            return None
        correct, total = value['correct'], value['total']
        if not _small_int(correct) or not _small_int(total):
            return None
        if 'response' not in value:
            code = _NO_RESPONSE
        else:
            response = value['response']
            if response == '':
                code = _EMPTY_RESPONSE
            elif isinstance(response, str) and len(response) == 1 and 32 <= ord(response) <= 126:
                code = ord(response)
            else:
                return None
        keys.append(key)
        data += bytes((_pack_int(correct), _pack_int(total), code))
    return tuple(keys), bytes(data)


class Record:
    """Um resultado de simulado de um aluno. Somente leitura."""

    __slots__ = ('id', 'user', 'key', 'activity', 'date', 'md', '_keys', '_data', '_raw', '_acc')

    def __init__(self, row, keys_cache):
        self.id = str(_get(row, 'id') or '')
        self.user = _get(row, 'user_id')
        self.key = str(_get(row, 'activity_key') or '')
        self.activity = str(_get(row, 'activity') or '')
        self.date = str(_get(row, 'applied_on') or '')
        self.md = _json(_get(row, 'metadata'))
        metrics = _json(_get(row, 'metrics'))
        packed = _compact(metrics)
        if packed is None:
            # Formato fora do comum: guarda como veio (raro).
            self._keys, self._data, self._raw = (), b'', metrics
        else:
            keys, data = packed
            # O mesmo conjunto de questões se repete em quase todos os resultados:
            # uma única tupla de chaves serve para todos.
            self._keys = keys_cache.setdefault(keys, keys)
            self._data, self._raw = data, None
        self._acc = None

    def metrics(self):
        """Dicionário no mesmo formato gravado no banco (sem o rótulo "name", que nenhum painel usa).

        Cada chamada monta um dicionário novo; quem chama pode descartá-lo logo depois.
        """
        if self._raw is not None:
            return self._raw
        out = {}
        data = self._data
        for index, key in enumerate(self._keys):
            base = 3 * index
            item = {'correct': _unpack_int(data[base]), 'total': _unpack_int(data[base + 1])}
            code = data[base + 2]
            if code == _EMPTY_RESPONSE:
                item['response'] = ''
            elif code != _NO_RESPONSE:
                item['response'] = chr(code)
            out[key] = item
        return out

    def items(self):
        """(chave, acertos, total) de cada questão, sem montar dicionários."""
        if self._raw is not None:
            for key, value in self._raw.items():
                yield key, value
            return
        data = self._data
        for index, key in enumerate(self._keys):
            base = 3 * index
            yield key, {'correct': _unpack_int(data[base]), 'total': _unpack_int(data[base + 1])}


def _metric_number(key):
    try:
        return int(str(key).split(':')[-1])
    except Exception:
        return None


def _default_area(number):
    if not number:
        return None
    return 'LC' if number <= 45 else 'CH' if number <= 90 else 'CN' if number <= 135 else 'MT' if number <= 180 else None


class Store:
    def __init__(self):
        self._lock = threading.Lock()
        self._records = []
        self._stamp = None
        self._built_at = 0.0
        self._exam_stamp = None
        self._area_maps = {}
        self._area_map_fn = None

    # ------------------------------------------------------------ carimbos

    @staticmethod
    def _perf_stamp(app, c):
        row = app.db.execute(c, "SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_performance").fetchone()
        return f"{_get(row, 'n')}:{_get(row, 'stamp')}"

    @staticmethod
    def _exams_stamp(app, c):
        row = app.db.execute(c, "SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_exams").fetchone()
        return f"{_get(row, 'n')}:{_get(row, 'stamp')}"

    def invalidate(self):
        with self._lock:
            self._stamp = None
            self._exam_stamp = None

    # ------------------------------------------------------------ resultados

    def records(self, app, c):
        """Todos os resultados, ordenados por data e simulado. Lista compartilhada: não altere."""
        stamp = self._perf_stamp(app, c)
        if stamp == self._stamp and time.time() - self._built_at < TTL:
            return self._records
        with self._lock:
            if stamp == self._stamp and time.time() - self._built_at < TTL:
                return self._records
            records = []
            keys_cache = {}
            last = ''
            while True:
                rows = app.db.execute(
                    c,
                    'SELECT id,user_id,activity_key,activity,applied_on,metrics,metadata '
                    'FROM hmay_performance WHERE id>? ORDER BY id LIMIT ' + str(PAGE),
                    (last,),
                ).fetchall()
                if not rows:
                    break
                for row in rows:
                    records.append(Record(row, keys_cache))
                last = str(_get(rows[-1], 'id'))
                if len(rows) < PAGE:
                    break
                del rows
            records.sort(key=lambda r: (r.date, r.activity, r.id))
            self._records = records
            self._stamp = stamp
            self._built_at = time.time()
            return records

    # ------------------------------------------------------------ mapas de área por prova

    def area_maps(self, app, c, builder):
        """Mapa questão→área de cada prova (hmay_exams.items), refeito só quando as provas mudam."""
        stamp = self._exams_stamp(app, c)
        if stamp == self._exam_stamp and builder is self._area_map_fn:
            return self._area_maps, stamp
        with self._lock:
            if stamp != self._exam_stamp or builder is not self._area_map_fn:
                self._area_maps = builder(app, c)
                self._exam_stamp = stamp
                self._area_map_fn = builder
            return self._area_maps, self._exam_stamp

    @staticmethod
    def accuracy(record, area_maps):
        """Acertos e questões válidas por área (ALL, LC, CH, CN, MT) de um resultado.

        Mesma regra de model_data._v3712_row_accuracy. Fica guardado no registro enquanto o
        mapa de áreas for o mesmo objeto (ele é trocado quando as provas mudam).
        """
        cached = record._acc
        if cached is not None and cached[0] is area_maps:
            return cached[1]
        exam_id = record.md.get('_exam_id')
        qmap = area_maps.get(str(exam_id if exam_id is not None else '').strip(), {})
        result = {key: {'correct': 0, 'valid': 0} for key in AREAS}
        for key, value in record.items():
            if not isinstance(value, dict):
                continue
            try:
                correct = max(0, int(value.get('correct') or 0))
                valid = max(0, int(value.get('total') or 0))
            except Exception:
                continue
            result['ALL']['correct'] += correct
            result['ALL']['valid'] += valid
            number = _metric_number(key)
            area = qmap.get(number)
            if not area:
                area = _default_area(number)
            if area in result:
                result[area]['correct'] += correct
                result[area]['valid'] += valid
        record._acc = (area_maps, result)
        return result


STORE = Store()
