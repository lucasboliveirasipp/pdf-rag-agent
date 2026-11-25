similarity_prompt = """
Você deve avaliar se duas perguntas são semanticamente semelhantes.

Pergunta Original: "{original_query}"
Nova Pergunta: "{new_query}"

Estas perguntas buscam a mesma informação? Considere o significado semântico, não apenas palavras iguais.
"""

planner_prompt = """Para a consulta fornecida: "{query}", identifique:
1. Os principais tópicos ou conceitos-chave relacionados à pergunta, incluindo conceitos mais amplos e relacionados
2. Critérios gerais para avaliar se um trecho do documento pode conter informações úteis (seja liberal na avaliação)
3. Palavras-chave que poderiam indicar conteúdo relacionado, mesmo que indiretamente
4. O texto da pergunta original do usuário

FEEDBACK DE TENTATIVA ANTERIOR:
{feedback}

Baseado neste feedback, amplie sua busca e flexibilize os critérios. Considere informações parciais ou relacionadas 
que podem contribuir para a resposta, mesmo que não a respondam completamente. O documento pode não conter 
exatamente o que buscamos, mas informações relacionadas podem ser úteis.
"""
            
base_prompt = """Para a consulta fornecida: "{query}", identifique:
1. Os principais tópicos ou conceitos-chave relacionados à pergunta, incluindo conceitos mais amplos e relacionados
2. Critérios gerais para avaliar se um trecho do documento pode conter informações úteis (seja liberal na avaliação)
3. Palavras-chave que poderiam indicar conteúdo relacionado, mesmo que indiretamente
4. O texto da pergunta original do usuário

Lembre-se que estamos buscando informações que podem ajudar a responder a pergunta, mesmo que não sejam perfeitas ou completas.
"""

evaluate_prompt_page = """
Você é um avaliador equilibrado que determina se uma página contém informações relevantes para uma consulta específica.

### Contexto de avaliação:
{evaluation_context}

### Metadados da página:
{page_metadata}

### Instruções:
1. Analise os metadados da página para determinar se esta página contém informações ESPECÍFICAS relacionadas à consulta.
2. Diferencie entre páginas que apenas mencionam o tema geral e páginas que abordam aspectos específicos da consulta.
3. Mantenha um equilíbrio: seja inclusivo o suficiente para não perder informações importantes, mas seletivo o suficiente para filtrar conteúdo genérico ou não relacionado.
4. Atribua uma pontuação de relevância de 1 a 10:
   - 1-3: Menciona apenas o tema geral sem detalhes específicos
   - 4-6: Contém algumas informações potencialmente úteis, mas limitadas
   - 7-10: Aborda diretamente aspectos específicos da consulta
5. Forneça um breve motivo para sua avaliação, identificando elementos específicos que tornam a página relevante ou não.
6. Atribua como relevante (True) se a pontuação for 6 ou superior, garantindo um equilíbrio entre inclusão e seletividade.
"""

extract_info_prompt = """
Você é um especialista em extração de informações úteis de textos.

### Contexto do que deve ser respondido:
{evaluation_context}

### Conteúdo bruto da página {page_number}:
{page_raw_text}

### Instruções:
1. Extraia QUALQUER informação que possa estar relacionada à consulta e conceitos fornecidos.
2. Seja INCLUSIVO - é melhor extrair informações potencialmente úteis do que ignorá-las.
3. Organize as informações em um texto coeso, incluindo contexto suficiente para compreensão.
4. Apenas deixe o texto vazio se a página não contiver ABSOLUTAMENTE NADA relacionado à consulta.
5. Inclua informações que possam ter relação indireta com a consulta.
6. NÃO invente informações que não estejam no texto.
7. Se encontrar informações parciais, extraia-as mesmo assim - elas podem ser úteis quando combinadas com outras páginas.
"""

reflexion_prompt = """
Você é um avaliador que analisa se o contexto recuperado oferece informações úteis para responder a uma consulta.

### Consulta do usuário:
{query}

### Conceitos relacionados:
{concepts}

### Contexto atual disponível:
{context}

### Instruções:
1. Analise se o contexto disponível fornece ALGUMA informação útil para responder à consulta, mesmo que parcialmente.
2. Considere responder com as informações disponíveis, mesmo que incompletas, se elas forem relevantes.
3. Apenas rejeite o contexto se ele for completamente irrelevante ou não contiver NENHUMA informação útil.
4. Lembre-se: uma resposta parcial ou informações relacionadas são melhores que nenhuma resposta.
5. Se encontrar qualquer informação que possa contribuir para a resposta, considere que a consulta PODE ser respondida.
"""

generate_answer_message = """
Você é um assistente prestativo e direto. Use apenas o contexto fornecido para responder à pergunta do usuário.
Se não encontrar a informação necessária no contexto, informe que não possui dados suficientes para responder.

Histórico de mensagens: {messages}

Contexto: {context}

Pergunta do usuário: {question}

Conceitos relacionados: {concepts}

Responda de forma clara e objetiva, usando apenas as informações do contexto fornecido.
Se o contexto não tiver informações responda que não tem dados para responder a pergunta.
Estruture sua resposta de acordo com os conceitos relacionados, organizando as informações de forma lógica.
"""

extract_prompt = """
Leia a página do um documento PDF e:
1) Gere uma lista dos tópicos encontrados.
2) Crie metadados descritivos sobre o conteúdo da página.

Os metadados devem fornecer informações claras sobre o conteúdo da página, para que alguém possa 
decidir se vale a pena ler a página completa para uma determinada consulta ou interesse.

Página: {page}
"""