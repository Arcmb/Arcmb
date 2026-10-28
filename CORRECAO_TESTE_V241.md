# Identificação da versão nos testes de inicialização

O verificador do arquivo único agora exige a versão exata 2.4.1, acompanhando a identificação da aplicação. A etapa final do build atualiza somente essa identificação; todas as verificações funcionais permanecem obrigatórias.

Depois da reconstrução limpa, foram executados 284 testes automatizados (todos aprovados) e os cinco verificadores da inicialização, em SQLite temporário: verify_release, verify_adaptive, verify_selective, verify_workbook e verify_coordinator. Todos passaram. Os testes em PostgreSQL devem ser confirmados nos logs da publicação.

Esta correção não altera senhas, dados reais nem o esquema do banco.
