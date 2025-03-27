package br.com.finance.FinancePro.financias.Transacoes.Service;
import br.com.finance.FinancePro.financias.Transacoes.Model.TransacaoModel;
import br.com.finance.FinancePro.financias.Transacoes.Repository.TransacaoRepository;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class TransacaoService {

    private final TransacaoRepository transacaoRepository;

    public TransacaoService(TransacaoRepository transacaoRepository) {this.transacaoRepository = transacaoRepository;}

    public List<TransacaoModel> getAll() {return transacaoRepository.findAll();}
    public TransacaoModel save(TransacaoModel transacaoModel) {return transacaoRepository.save(transacaoModel);}
    public void delete(Long id) {transacaoRepository.deleteById(id);}
}
